# Copyright (c) Meta Platforms, Inc. and affiliates.

# All rights reserved.

#

# This source code is licensed under the BSD-style license found in the

# LICENSE file in the root directory of this source tree.



"""
FastAPI application for the Incidentops Env Environment.
This module creates an HTTP server that exposes the IncidentopsEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.
Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""
from __future__ import annotations
from fastapi import HTTPException, Request
from openenv.core.env_server.http_server import create_app

try:
    from ..models import IncidentopsAction, IncidentopsObservation
    from incidentops_env_environment import IncidentopsEnvironment
except Exception:
    from models import IncidentopsAction, IncidentopsObservation
    from server.incidentops_env_environment import IncidentopsEnvironment


# ✅ Single shared env instance used by BOTH create_app and /grade
_shared_env = IncidentopsEnvironment()

app = create_app(
    lambda: _shared_env,   # ← pass a factory that returns same instance
    IncidentopsAction,
    IncidentopsObservation,
    env_name="incidentops_env",
    max_concurrent_envs=1,
)
from graders import IncidentEasyGrader, IncidentMediumGrader, IncidentHardGrader

GRADERS = {
    "incident_easy": IncidentEasyGrader(),
    "incident_medium": IncidentMediumGrader(),
    "incident_hard": IncidentHardGrader(),
}

@app.get("/grade")
@app.post("/grade")
async def grade_endpoint(task_id: str = None, request: Request = None):
    try:
        # ✅ STRICT validation (important)
        if not task_id or task_id not in GRADERS:
            return {
                "score": 0.0,
                "success": False,
                "detail": "invalid or missing task_id"
            }

        snapshot = _shared_env._snapshot

        if snapshot is None:
            return {
                "score": 0.0,
                "success": False,
                "grader": task_id,
                "detail": "no active episode"
            }

        # ✅ Build trajectory
        trajectory = [
            {
                "action": a,
                "observation": {
                    "incident_resolved": snapshot.resolved
                }
            }
            for a in snapshot.action_history
        ]

        # ✅ Call correct grader
        score = GRADERS[task_id].grade(trajectory)

        return {
            "score": score,
            "success": score >= 0.5,
            "grader": task_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/tasks")
async def list_tasks():
    return {
        "tasks": [
            {"id": "incident_easy",   "name": "Single Service Outage (Easy)"},
            {"id": "incident_medium", "name": "Dependency Failure (Medium)"},
            {"id": "incident_hard",   "name": "Multi-Service Root Cause (Hard)"},
        ]
    }

def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()