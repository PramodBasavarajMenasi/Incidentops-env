import sys
print("1. Script started", flush=True)
print("2. Testing imports...", flush=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("3. dotenv OK", flush=True)
except Exception as e:
    print(f"3. dotenv error: {e}", flush=True)

try:
    import httpx
    print("4. httpx OK", flush=True)
except Exception as e:
    print(f"4. httpx FAILED: {e}", flush=True)
    sys.exit(1)

try:
    from openai import OpenAI
    print("5. openai OK", flush=True)
except Exception as e:
    print(f"5. openai FAILED: {e}", flush=True)
    sys.exit(1)

import os
print(f"6. HF_TOKEN={'set' if os.getenv('HF_TOKEN') else 'missing'}", flush=True)

print("7. Testing server...", flush=True)

try:
    r = httpx.get("http://localhost:8000/tasks", timeout=5.0)
    print(f"8. Server response: {r.status_code}", flush=True)
except Exception as e:
    print(f"8. Server error: {e}", flush=True)
    sys.exit(1)

print("9. Testing reset...", flush=True)

try:
    r = httpx.post("http://localhost:8000/reset", json={"task_id": "incident_easy"}, timeout=5.0)
    print(f"10. Reset status: {r.status_code}", flush=True)
    data = r.json()
    obs = data.get("observation", data)
    print(f"11. Alert: {obs.get('alert_summary', 'N/A')[:50]}", flush=True)
except Exception as e:
    print(f"10. Reset error: {e}", flush=True)
    sys.exit(1)

print("12. Testing step...", flush=True)

try:
    r = httpx.post(
        "http://localhost:8000/step",
        json={"action": {"action": "rollback_deploy"}},
        timeout=5.0,
    )
    print(f"13. Step status: {r.status_code}", flush=True)
    print(f"14. Step body: {r.text[:200]}", flush=True)
except Exception as e:
    print(f"13. Step error: {e}", flush=True)

print("15. Testing grade...", flush=True)

try:
    r = httpx.get("http://localhost:8000/grade", params={"task_id": "incident_easy"}, timeout=5.0)
    print(f"16. Grade status: {r.status_code}", flush=True)
    print(f"17. Grade body: {r.text[:200]}", flush=True)
except Exception as e:
    print(f"16. Grade error: {e}", flush=True)

print("18. ALL DONE", flush=True)