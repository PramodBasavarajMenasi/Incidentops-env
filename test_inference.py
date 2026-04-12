import sys
print("Script started", flush=True)
print(f"Python: {sys.executable}", flush=True)

try:
    import httpx
    print("httpx imported OK", flush=True)
except ImportError as e:
    print(f"httpx import FAILED: {e}", flush=True)

try:
    from openai import OpenAI
    print("openai imported OK", flush=True)
except ImportError as e:
    print(f"openai import FAILED: {e}", flush=True)

try:
    from models import IncidentopsAction, IncidentopsObservation
    print("models imported OK", flush=True)
except ImportError as e:
    print(f"models import FAILED: {e}", flush=True)

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("dotenv loaded OK", flush=True)
except ImportError:
    print("dotenv not available (OK)", flush=True)

import os
print(f"HF_TOKEN set: {bool(os.getenv('HF_TOKEN'))}", flush=True)
print(f"API_KEY set: {bool(os.getenv('API_KEY'))}", flush=True)

import httpx
print("\nTesting server connection...", flush=True)
try:
    r = httpx.get("http://localhost:8000/tasks", timeout=5.0)
    print(f"  /tasks status: {r.status_code}", flush=True)
    print(f"  /tasks body: {r.text}", flush=True)
except Exception as e:
    print(f"  Server error: {e}", flush=True)

try:
    r = httpx.post("http://localhost:8000/reset", json={"task_id": "incident_easy"}, timeout=5.0)
    print(f"  /reset status: {r.status_code}", flush=True)
    print(f"  /reset body: {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  Reset error: {e}", flush=True)

try:
    r = httpx.post("http://localhost:8000/step", json={"action": "rollback_deploy"}, timeout=5.0)
    print(f"  /step status: {r.status_code}", flush=True)
    print(f"  /step body: {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  Step error: {e}", flush=True)

print("\nAll checks done!", flush=True)