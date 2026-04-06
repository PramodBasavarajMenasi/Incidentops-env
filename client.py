# Copyright (c) Meta Platforms, Inc. and affiliates.

# All rights reserved.

#

# This source code is licensed under the BSD-style license found in the

# LICENSE file in the root directory of this source tree.

"""Incidentops Env Environment Client."""
from __future__ import annotations
from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State
from models import IncidentopsAction, IncidentopsObservation

class IncidentopsEnv(EnvClient[IncidentopsAction, IncidentopsObservation, State]):
    def _step_payload(self, action: IncidentopsAction) -> Dict:
        return {"action": action.action}

    def _parse_result(self, payload: Dict) -> StepResult[IncidentopsObservation]:
        obs_data = payload.get("observation", {})
        observation = IncidentopsObservation(
            alert_summary=obs_data.get("alert_summary", ""),
            severity=obs_data.get("severity", "low"),
            likely_cause=obs_data.get("likely_cause", "unknown"),
            hf_confidence=obs_data.get("hf_confidence", 0.0),
            services_affected=obs_data.get("services_affected", []),
            logs_available=obs_data.get("logs_available", False),
            log_snippet=obs_data.get("log_snippet", ""),
            service_healthy=obs_data.get("service_healthy", False),
            elapsed_steps=obs_data.get("elapsed_steps", 0),
            sla_steps_remaining=obs_data.get("sla_steps_remaining", 0),
            action_history=obs_data.get("action_history", []),
            available_actions=obs_data.get("available_actions", []),
            incident_resolved=obs_data.get("incident_resolved", False),
            wrong_escalations=obs_data.get("wrong_escalations", 0),
            metadata=obs_data.get("metadata", {}),
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )
        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )

