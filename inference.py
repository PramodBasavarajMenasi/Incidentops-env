import json
import os
import sys
import traceback

print("[DEBUG] line 6", flush=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

print("[DEBUG] line 14", flush=True)

import httpx

print("[DEBUG] line 18", flush=True)

from openai import OpenAI

print("[DEBUG] line 22", flush=True)

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
BENCHMARK = "incidentops_env"
TASK_IDS = ["incident_easy", "incident_medium", "incident_hard"]
ENV_URL = os.getenv("ENV_URL", "http://localhost:8000")
MAX_STEPS = 12
TEMPERATURE = 0.2

print("[DEBUG] line 33", flush=True)


def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step, action, reward, done, error):
    err = error if error else "null"
    d = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={d} error={err}", flush=True)


def log_end(success, steps, score, rewards):
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.2f} rewards={rewards_str}", flush=True)


def choose_action(obs):
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


def run_task(http, task_id):
    print(f"[DEBUG] Starting task: {task_id}", flush=True)
    rewards = []
    steps_taken = 0
    success = False
    score = 0.0

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        r = http.post(f"{ENV_URL}/reset", json={"task_id": task_id}, timeout=30.0)
        r.raise_for_status()
        obs = extract_obs(r.json())
        print(f"[DEBUG] Reset OK: cause={obs.get('likely_cause')}", flush=True)

        finished = obs.get("done", False) or obs.get("incident_resolved", False)

        for step in range(1, MAX_STEPS + 1):
            if finished:
                break

            action_name = choose_action(obs)
            print(f"[DEBUG] Step {step}: {action_name}", flush=True)

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

        r = http.get(f"{ENV_URL}/grade", params={"task_id": task_id}, timeout=30.0)
        r.raise_for_status()
        grade = r.json()
        score = float(grade.get("score", 0.0))
        success = bool(grade.get("success", False))
        print(f"[DEBUG] Grade: {grade}", flush=True)

    except Exception as e:
        print(f"[DEBUG] Error: {e}", flush=True)
        traceback.print_exc()

    finally:
        log_end(success, steps_taken, score, rewards)


print("[DEBUG] line 137 - about to define main", flush=True)


def main():
    print(f"[DEBUG] main() called", flush=True)
    print(f"[DEBUG] ENV_URL={ENV_URL}", flush=True)

    http = httpx.Client()

    try:
        r = http.get(f"{ENV_URL}/tasks", timeout=10.0)
        print(f"[DEBUG] Server OK: {r.status_code}", flush=True)
    except Exception as e:
        print(f"[ERROR] Server not running: {e}", flush=True)
        return

    for task_id in TASK_IDS:
        run_task(http, task_id)

    http.close()
    print("[DEBUG] Done!", flush=True)


print("[DEBUG] line 160 - about to check name", flush=True)
print(f"[DEBUG] name = {__name__}", flush=True)

if __name__ == "__main__":
    print("[DEBUG] entering main()", flush=True)
    try:
        main()
    except Exception as e:
        print(f"[FATAL] {e}", flush=True)
        traceback.print_exc()