from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from models import IncidentopsAction, IncidentopsObservation
except ImportError:
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


# Scenarios
SCENARIOS: Dict[str, List[Dict[str, Any]]] = {
    "incident_easy": [
        {
            "scenario_id": "easy_001",
            "task": "incident_easy",
            "alert_text": "SEV-2: payment-service latency high after deploy.",
            "hidden_truth": "bad_deployment",
            "severity": "high",
            "affected_services": ["payment-service"],
            "logs_available": True,
            "log_snippet": "deploy at 14:32 UTC caused connection pool exhaustion",
            "likely_cause": "bad_deployment",
            "hf_confidence": 0.92,
            "available_actions": [
                "request_logs",
                "rollback_deploy",
                "restart_service",
                "resolve_incident",
            ],
            "correct_action_sequence": [
                "rollback_deploy",
                "resolve_incident",
            ],
            "sla_steps": 5,
        }
    ],
    "incident_medium": [
        {
            "scenario_id": "medium_001",
            "task": "incident_medium",
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
            "correct_action_sequence": [
                "request_logs",
                "query_dependencies",
                "escalate_db_team",
                "restart_service",
                "resolve_incident",
            ],
            "sla_steps": 8,
        }
    ],
    "incident_hard": [
        {
            "scenario_id": "hard_001",
            "task": "incident_hard",
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


#  Main Environment Class
class IncidentopsEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def init(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self._snapshot: Optional[IncidentSnapshot] = None
        self._difficulty = "incident_easy"
        self._last_observation: Optional[IncidentopsObservation] = None

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
    
    # Reward
    def _calc_reward(self, action: str) -> float:
        assert self._snapshot is not None
        s = self._snapshot

        reward = -0.05

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
                if s.step_count <= s.sla_steps and (
                    s.evidence_collected or s.team_engaged is not None or s.hidden_truth == "bad_deployment"
                ):
                    reward += 1.5
                    s.resolved = True
                else:
                    reward -= 2.0
            else:
                reward -= 1.0

        if s.step_count > s.sla_steps:
            reward -= 0.5

        return reward

    # ReSet
    def reset(self, episode_id=None, task_id="incident_easy", **kwargs):
        print(f"[ENV] reset called: task_id={task_id}", flush=True)
        scenarios = SCENARIOS.get(task_id, SCENARIOS["incident_easy"])
        scenario = scenarios[0]

        self._state = State(episode_id=episode_id or str(uuid4()), step_count=0)
        self._snapshot = IncidentSnapshot(**scenario)
        self._snapshot.action_history = []

        self._last_observation = self._build_observation()
        return self._last_observation

    # Step
    def step(self, action) -> IncidentopsObservation:
        """Handle step - accept both IncidentopsAction objects and dicts."""
        print(f"[ENV] step called: action={action}, type={type(action)}", flush=True)

        if isinstance(action, IncidentopsAction):
            action_name = action.action
        elif isinstance(action, dict):
            action_name = action.get("action", "resolve_incident")
        elif isinstance(action, str):
            action_name = action
        else:
            action_name = str(action)

        print(f"[ENV] action_name={action_name}", flush=True)

        if self._snapshot is None:
            print("[ENV] ERROR: No snapshot! Calling reset first.", flush=True)
            self.reset()

        assert self._snapshot is not None

        self._snapshot.step_count += 1
        self._state.step_count = self._snapshot.step_count

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

        if done:
            grade_result = self.grade()
            obs.metadata["grader_score"] = grade_result["score"]

        self._last_observation = obs
        print(f"[ENV] step done: reward={reward:.2f}, done={done}", flush=True)
        return obs

    # Grade
    def grade(self) -> dict:
        assert self._snapshot is not None
        s = self._snapshot

        total_steps = max(s.step_count, 1)
        sla_ok = s.step_count <= s.sla_steps
        correct_actions = sum(
            1 for a in s.action_history if a in s.correct_action_sequence
        )
        correctness_ratio = correct_actions / max(len(s.correct_action_sequence), 1)
        efficiency_bonus = max(0.0, (s.sla_steps - total_steps) / s.sla_steps)

        if s.resolved and sla_ok:
            score = min(1.0, 0.5 + 0.3 * correctness_ratio + 0.2 * efficiency_bonus)
        elif s.resolved:
            score = min(0.6, 0.3 + 0.3 * correctness_ratio)
        else:
            score = max(0.0, 0.1 * correctness_ratio)

        return {
            "score": round(score, 4),
            "success": s.resolved and sla_ok,
            "incident_resolved": s.resolved,
            "steps_taken": s.step_count,
            "sla_met": sla_ok,
            "efficiency_bonus": round(efficiency_bonus, 4),
            "wrong_escalations": s.wrong_escalations,
            "evidence_collected": s.evidence_collected,
        }

    @property
    def state(self) -> State:
        return self._state