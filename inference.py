import json
import os
import sys
import traceback

import httpx
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_BASE_URL = os.environ.get("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.environ.get("API_KEY", "") or os.environ.get("HF_TOKEN", "")
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

BENCHMARK = "incidentops_env"
TASK_IDS = ["incident_easy", "incident_medium", "incident_hard"]
ENV_URL = os.environ.get("ENV_URL", "http://localhost:8000")
MAX_STEPS = 12
TEMPERATURE = 0.2

SYSTEM_PROMPT = """You are an expert incident-response engineer.
You are given an incident observation with alert details, severity, affected services, and available actions.
Analyze the situation and choose the BEST single action from the available_actions list.

Rules:
- If logs are not available, request_logs first
- Investigate before escalating
- Escalate to the correct team based on evidence
- Resolve only when the incident is actually fixed
- Minimize steps to stay within SLA

Return ONLY the action string, nothing else. No explanation, no quotes."""


def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step, action, reward, done, error):
    err = error if error else "null"
    d = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={d} error={err}", flush=True)


def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


def choose_action_llm(client, obs):
    """Always call the LLM first, fall back to deterministic only on error."""
    available = obs.get("available_actions", [])
    if not available:
        return "resolve_incident"

    obs_for_llm = {
        "alert_summary": obs.get("alert_summary", ""),
        "severity": obs.get("severity", ""),
        "likely_cause": obs.get("likely_cause", ""),
        "hf_confidence": obs.get("hf_confidence", 0.0),
        "logs_available": obs.get("logs_available", False),
        "log_snippet": obs.get("log_snippet", ""),
        "services_affected": obs.get("services_affected", []),
        "elapsed_steps": obs.get("elapsed_steps", 0),
        "sla_steps_remaining": obs.get("sla_steps_remaining", 0),
        "action_history": obs.get("action_history", []),
        "available_actions": available,
        "incident_resolved": obs.get("incident_resolved", False),
        "wrong_escalations": obs.get("wrong_escalations", 0),
    }

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(obs_for_llm)},
            ],
            temperature=TEMPERATURE,
            max_tokens=20,
        )
        text = (response.choices[0].message.content or "").strip()
      
        text = text.splitlines()[0].strip().strip("'\"` ")

        if text in available:
            return text

       
        for action in available:
            if action in text or text in action:
                return action

    except Exception as e:
        print(f"[DEBUG] LLM call error: {e}", flush=True)

    
    return choose_action_deterministic(obs)


def choose_action_deterministic(obs):
    """Fallback deterministic policy."""
    available = obs.get("available_actions", [])
    logs_available = obs.get("logs_available", False)
    likely_cause = obs.get("likely_cause", "unknown")

    if not available:
        return "resolve_incident"
    if not logs_available and "request_logs" in available:
        return "request_logs"
    if likely_cause == "bad_deployment" and "rollback_deploy" in available:
        return "rollback_deploy"
    if likely_cause == "dependency_issue" and "query_dependencies" in available:
        return "query_dependencies"
    if likely_cause == "ambiguous" and "query_region_health" in available:
        return "query_region_health"
    if likely_cause == "dns_issue" and "query_dns_status" in available:
        return "query_dns_status"
    if likely_cause == "db_timeout" and "escalate_db_team" in available:
        return "escalate_db_team"
    if likely_cause == "dns_issue" and "escalate_network_team" in available:
        return "escalate_network_team"
    if likely_cause == "dns_issue" and "broadcast_status_page" in available:
        return "broadcast_status_page"
    if "restart_service" in available and likely_cause in ("db_timeout", "bad_deployment"):
        return "restart_service"
    if "resolve_incident" in available:
        return "resolve_incident"
    return available[0] if available else "resolve_incident"


def extract_obs(data):
    if "observation" in data:
        obs = data["observation"]
    else:
        obs = data
    if isinstance(obs, str):
        obs = json.loads(obs)
    return obs


def run_task(client, http, task_id):
    rewards = []
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
      
        r = http.post(f"{ENV_URL}/reset", json={"task_id": task_id}, timeout=30.0)
        r.raise_for_status()
        obs = extract_obs(r.json())

        finished = obs.get("done", False) or obs.get("incident_resolved", False)

        for step in range(1, MAX_STEPS + 1):
            if finished:
                break

          
            action_name = choose_action_llm(client, obs)

          
            r = http.post(
                f"{ENV_URL}/step",
                json={"action": {"action": action_name}},
                timeout=30.0,
            )
            r.raise_for_status()
            step_data = r.json()
            obs = extract_obs(step_data)

            reward = float(step_data.get("reward", obs.get("reward", 0.0)))
            finished = bool(
                step_data.get("done", obs.get("done", False))
                or obs.get("incident_resolved", False)
            )

            rewards.append(reward)
            steps_taken = step
            log_step(step, action_name, reward, finished, None)

      
        try:
            r = http.get(f"{ENV_URL}/grade", params={"task_id": task_id}, timeout=30.0)
            r.raise_for_status()
            grade = r.json()
            score = float(grade.get("score", 0.0))
            success = bool(grade.get("success", False))
        except Exception as e:
            print(f"[DEBUG] Grade error: {e}", flush=True)
            success = obs.get("incident_resolved", False)
            score = max(0.0, min(1.0, sum(rewards) / 5.0))

    except Exception as e:
        print(f"[DEBUG] Error in task {task_id}: {e}", flush=True)
        traceback.print_exc()

    finally:
        log_end(success, steps_taken, score, rewards)


def main():
    if not API_KEY:
        print("[ERROR] No API_KEY or HF_TOKEN set!", flush=True)
        sys.exit(1)

    client = OpenAI(
        base_url=API_BASE_URL,
        api_key=API_KEY,
    )

    http = httpx.Client()


    try:
        r = http.get(f"{ENV_URL}/tasks", timeout=10.0)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERROR] Server not reachable: {e}", flush=True)
        for tid in TASK_IDS:
            log_start(task=tid, env=BENCHMARK, model=MODEL_NAME)
            log_end(False, 0, 0.0, [])
        return

  
    for task_id in TASK_IDS:
        run_task(client, http, task_id)

    http.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FATAL] {e}", flush=True)
        traceback.print_exc()