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
from openenv.core.env_server.http_server import create_app
try:
    from ..models import IncidentopsAction, IncidentopsObservation
    from incidentops_env_environment import IncidentopsEnvironment
except Exception:
    from models import IncidentopsAction, IncidentopsObservation
    from server.incidentops_env_environment import IncidentopsEnvironment

app = create_app(
    IncidentopsEnvironment,
    IncidentopsAction,
    IncidentopsObservation,
    env_name="incidentops_env",
    max_concurrent_envs=1,
)

def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()