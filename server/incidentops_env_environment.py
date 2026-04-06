# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Incidentops Env Environment Implementation.

A simple test environment that echoes back messages sent to it.
Perfect for testing HTTP server infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import IncidentopsAction, IncidentopsObservation
except Exception:
    from models import IncidentopsAction, IncidentopsObservation


@dataclass
class IncidentSnapshot:
    scenario_id: str
    task: str
    alert_text: str
    hidden_truth: str
    severity: str
    affected_services: List[str]
    logs_available: bool
    log_snippet: str
    likely_cause: str
    hf_confidence: float
    available_actions: List[str]
    correct_action_sequence: List[str]
    sla_steps: int
    step_count: int = 0
    resolved: bool = False
    wrong_escalations: int = 0
    action_history: List[str] = field(default_factory=list)
    evidence_collected: bool = False
    team_engaged: Optional[str] = None


SCENARIOS: Dict[str, List[Dict[str, Any]]] = {
    "easy": [
        {
            "scenario_id": "easy_001",
            "task": "single_service_outage",
            "alert_text": "SEV-2: payment-service latency high after deploy.",
            "hidden_truth": "bad_deployment",
            "severity": "high",
            "affected_services": ["payment-service"],
            "logs_available": True,
            "log_snippet": "deploy at 14:32 UTC caused connection pool exhaustion",
            "likely_cause": "bad_deployment",
            "hf_confidence": 0.92,
            "available_actions": ["request_logs", "rollback_deploy", "restart_service", "resolve_incident"],
            "correct_action_sequence": ["rollback_deploy", "resolve_incident"],
            "sla_steps": 5,
        }
    ],
    "medium": [
        {
            "scenario_id": "medium_001",
            "task": "dependency_failure",
            "alert_text": "SEV-1: api-gateway 5xx errors; user-profile-service slow; no logs available.",
            "hidden_truth": "db_timeout",
            "severity": "critical",
            "affected_services": ["api-gateway", "user-profile-service"],
            "logs_available": False,
            "log_snippet": "DB timeout errors from checkout reads",
            "likely_cause": "dependency_issue",
            "hf_confidence": 0.72,
            "available_actions": [
                "request_logs",
                "query_dependencies",
                "escalate_db_team",
                "escalate_network_team",
                "restart_service",
                "resolve_incident",
            ],
            "correct_action_sequence": ["request_logs", "query_dependencies", "escalate_db_team", "restart_service", "resolve_incident"],
            "sla_steps": 8,
        }
    ],
    "hard": [
        {
            "scenario_id": "hard_001",
            "task": "multi_service_root_cause",
            "alert_text": "SEV-1: EU checkout failures. Auth and payment degraded. Logs incomplete.",
            "hidden_truth": "dns_issue",
            "severity": "critical",
            "affected_services": ["auth-service", "payment-service", "checkout-service"],
            "logs_available": False,
            "log_snippet": "DNS query failures in EU region resolver",
            "likely_cause": "ambiguous",
            "hf_confidence": 0.55,
            "available_actions": [
                "request_logs",
                "query_dns_status",
                "query_region_health",
                "rollback_deploy",
                "restart_service",
                "escalate_network_team",
                "escalate_db_team",
                "broadcast_status_page",
                "resolve_incident",
            ],
            "correct_action_sequence": [
                "query_region_health",
                "query_dns_status",
                "escalate_network_team",
                "broadcast_status_page",
                "resolve_incident",
            ],
            "sla_steps": 12,
        }
    ],
}


class IncidentopsEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._snapshot: Optional[IncidentSnapshot] = None
        self._difficulty = "easy"
        self._last_observation: Optional[IncidentopsObservation] = None

    def _pick_scenario(self, difficulty: str) -> Dict[str, Any]:
        scenarios = SCENARIOS.get(difficulty, SCENARIOS["easy"])
        return scenarios[0]

    def _build_observation(self) -> IncidentopsObservation:
        assert self._snapshot is not None
        remaining = max(self._snapshot.sla_steps - self._snapshot.step_count, 0)
        return IncidentopsObservation(
            alert_summary=self._snapshot.alert_text,
            severity=self._snapshot.severity,
            likely_cause=self._snapshot.likely_cause,
            hf_confidence=self._snapshot.hf_confidence,
            services_affected=self._snapshot.affected_services,
            logs_available=self._snapshot.logs_available,
            log_snippet=self._snapshot.log_snippet if self._snapshot.logs_available else "",
            service_healthy=self._snapshot.resolved,
            elapsed_steps=self._snapshot.step_count,
            sla_steps_remaining=remaining,
            action_history=list(self._snapshot.action_history),
            available_actions=self._snapshot.available_actions,
            incident_resolved=self._snapshot.resolved,
            wrong_escalations=self._snapshot.wrong_escalations,
            metadata={
                "scenario_id": self._snapshot.scenario_id,
                "task": self._snapshot.task,
                "hidden_truth": self._snapshot.hidden_truth,
                "team_engaged": self._snapshot.team_engaged,
                "evidence_collected": self._snapshot.evidence_collected,
            },
            reward=0.0,
            done=self._snapshot.resolved,
        )

    def _calc_reward(self, action: str) -> float:
        assert self._snapshot is not None
        s = self._snapshot

        reward = -0.05  # small step cost

        if s.action_history.count(action) > 1:
            reward -= 0.2

        if action == "request_logs" and not s.logs_available:
            reward += 0.3
            s.logs_available = True
            s.evidence_collected = True

        if action == "query_dependencies" and s.hidden_truth == "db_timeout":
            reward += 0.5
            s.likely_cause = "db_timeout"
            s.hf_confidence = min(0.95, s.hf_confidence + 0.15)
            s.evidence_collected = True

        if action == "query_dns_status" and s.hidden_truth == "dns_issue":
            reward += 0.5
            s.likely_cause = "dns_issue"
            s.hf_confidence = min(0.95, s.hf_confidence + 0.20)
            s.evidence_collected = True

        if action == "query_region_health" and s.hidden_truth == "dns_issue":
            reward += 0.4
            s.hf_confidence = min(0.95, s.hf_confidence + 0.10)

        if action == "rollback_deploy" and s.hidden_truth == "bad_deployment":
            reward += 1.0
            s.resolved = True
        elif action == "rollback_deploy":
            reward -= 0.8

        if action == "escalate_db_team" and s.hidden_truth == "db_timeout":
            reward += 0.7
            s.team_engaged = "db_team"
        elif action == "escalate_db_team":
            reward -= 0.5
            s.wrong_escalations += 1

        if action == "escalate_network_team" and s.hidden_truth == "dns_issue":
            reward += 0.7
            s.team_engaged = "network_team"
        elif action == "escalate_network_team":
            reward -= 0.5
            s.wrong_escalations += 1

        if action == "broadcast_status_page":
            reward += 0.2 if s.step_count <= 2 else 0.05

        if action == "restart_service" and s.hidden_truth in {"bad_deployment", "db_timeout"}:
            reward += 0.8
        elif action == "restart_service":
            reward -= 0.2

        if action == "resolve_incident":
            if s.resolved or s.hidden_truth in {"bad_deployment", "db_timeout", "dns_issue"}:
                if s.step_count <= s.sla_steps and (s.evidence_collected or s.team_engaged is not None or s.hidden_truth == "bad_deployment"):
                    reward += 1.5
                    s.resolved = True
                else:
                    reward -= 2.0
            else:
                reward -= 1.0

        if s.step_count > s.sla_steps:
            reward -= 0.5

        return reward

    def reset(self, difficulty: str = "easy") -> IncidentopsObservation:
        scenario = self._pick_scenario(difficulty)
        self._difficulty = difficulty
        self._state = State(episode_id=str(uuid4()), step_count=0)

        self._snapshot = IncidentSnapshot(**scenario)

        # ✅ FORCE CLEAN (important)
        self._snapshot.action_history = []

        self._last_observation = self._build_observation()
        return self._last_observation

    def step(self, action: IncidentopsAction) -> IncidentopsObservation:  # type: ignore[override]
        assert self._snapshot is not None
        self._snapshot.step_count += 1
        self._state.step_count = self._snapshot.step_count

        action_name = action.action
        self._snapshot.action_history.append(action_name)

        reward = self._calc_reward(action_name)
        done = self._snapshot.resolved or self._snapshot.step_count >= self._snapshot.sla_steps

        obs = self._build_observation()
        obs.reward = reward
        obs.done = done
        obs.metadata = {
            **(obs.metadata or {}),
            "last_action": action_name,
            "last_reward": reward,
        }
        self._last_observation = obs
        return obs

    @property
    def state(self) -> State:
        return self._state
