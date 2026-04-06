from __future__ import annotations
from dotenv import load_dotenv
import os

load_dotenv()
import asyncio
import json
import os
from typing import List, Optional

from openai import OpenAI

from client import IncidentopsEnv
from models import IncidentopsAction

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
TASK_NAME = os.getenv("INCIDENTOPS_TASK", "incidentops")
BENCHMARK = os.getenv("INCIDENTOPS_BENCHMARK", "incidentops_env")
MAX_STEPS = int(os.getenv("MAX_STEPS", "12"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")
DIFFICULTY = os.getenv("DIFFICULTY", "easy")

SYSTEM_PROMPT = """
You are an incident-response policy.
Choose exactly one action from the environment's available actions.
Prefer investigation when confidence is low.
Prefer mitigation or escalation when evidence points to a cause.
Return only the action string.
""".strip()


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={error if error else 'null'}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


def choose_action(client: OpenAI, obs) -> str:
    available = obs.available_actions or []
    if not available:
        return "resolve_incident"

    prompt = {
        "alert_summary": obs.alert_summary,
        "severity": obs.severity,
        "likely_cause": obs.likely_cause,
        "hf_confidence": obs.hf_confidence,
        "logs_available": obs.logs_available,
        "log_snippet": obs.log_snippet,
        "services_affected": obs.services_affected,
        "elapsed_steps": obs.elapsed_steps,
        "sla_steps_remaining": obs.sla_steps_remaining,
        "action_history": obs.action_history,
        "available_actions": available,
    }

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(prompt)},
        ],
        temperature=TEMPERATURE,
        max_tokens=20,
    )
    text = (response.choices[0].message.content or "").strip().splitlines()[0].strip()

    if text in available:
        return text

    # fallback heuristics
    if not obs.logs_available and "request_logs" in available:
        return "request_logs"
    if obs.likely_cause == "dns_issue" and "query_dns_status" in available:
        return "query_dns_status"
    if obs.likely_cause == "dependency_issue" and "query_dependencies" in available:
        return "query_dependencies"
    if obs.hf_confidence < 0.7 and "query_region_health" in available:
        return "query_region_health"
    if "resolve_incident" in available and (obs.service_healthy or obs.incident_resolved):
        return "resolve_incident"
    return available[0]


async def main() -> None:
    if not API_KEY:
        raise RuntimeError("Missing HF_TOKEN/API_KEY/OPENAI_API_KEY")

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    env = await IncidentopsEnv.from_docker_image(os.getenv("IMAGE_NAME")) if os.getenv("IMAGE_NAME") else IncidentopsEnv(base_url=ENV_URL)

    rewards: List[float] = []
    steps_taken = 0
    success = False
    score = 0.0

    log_start(TASK_NAME, BENCHMARK, MODEL_NAME)

    try:
        result = await env.reset(difficulty=DIFFICULTY)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            action_name = choose_action(client, obs)
            result = await env.step(IncidentopsAction(action=action_name))
            obs = result.observation
            reward = float(result.reward or 0.0)
            done = bool(result.done)

            rewards.append(reward)
            steps_taken = step
            log_step(step, action_name, reward, done, None)

            if done:
                break

        total_reward = sum(rewards)
        score = max(0.0, min(1.0, total_reward / 5.0))
        success = bool(obs.incident_resolved) and score >= 0.1

    finally:
        try:
            await env.close()
        except Exception:
            pass
        log_end(success, steps_taken, score, rewards)


if __name__ == "__main__":
    asyncio.run(main())
