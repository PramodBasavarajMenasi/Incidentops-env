"""Graders for the Incidentops environment."""

from __future__ import annotations
from typing import Any, Dict, List


class BaseIncidentGrader:
    """Base grader with shared logic."""

    task_id: str = ""
    expected_actions: List[str] = []
    sla_steps: int = 10

    def grade(self, trajectory: List[Dict[str, Any]]) -> float:
        """
        Grade a trajectory of (action, observation) pairs.
        Returns a score in [0.0, 1.0].
        """
        if not trajectory:
            return 0.0

        actions_taken = []
        resolved = False
        wrong_escalations = 0

        for entry in trajectory:
            action = entry.get("action", "")
            if isinstance(action, dict):
                action = action.get("action", "")
            actions_taken.append(action)

            obs = entry.get("observation", {})
            if isinstance(obs, dict):
                resolved = obs.get("incident_resolved", False)

        total_steps = len(actions_taken)

        # Correctness: how many correct actions were taken
        correct_actions = sum(
            1 for a in actions_taken if a in self.expected_actions
        )
        correctness_ratio = correct_actions / max(len(self.expected_actions), 1)

        # Efficiency bonus
        efficiency_bonus = max(0.0, (self.sla_steps - total_steps) / self.sla_steps)

        sla_ok = total_steps <= self.sla_steps

        if resolved and sla_ok:
            score = min(1.0, 0.5 + 0.3 * correctness_ratio + 0.2 * efficiency_bonus)
        elif resolved:
            score = min(0.6, 0.3 + 0.3 * correctness_ratio)
        else:
            score = max(0.0, 0.1 * correctness_ratio)

        return round(score, 4)


class IncidentEasyGrader(BaseIncidentGrader):
    task_id = "incident_easy"
    expected_actions = ["rollback_deploy", "resolve_incident"]
    sla_steps = 5


class IncidentMediumGrader(BaseIncidentGrader):
    task_id = "incident_medium"
    expected_actions = [
        "request_logs",
        "query_dependencies",
        "escalate_db_team",
        "restart_service",
        "resolve_incident",
    ]
    sla_steps = 8


class IncidentHardGrader(BaseIncidentGrader):
    task_id = "incident_hard"
    expected_actions = [
        "query_region_health",
        "query_dns_status",
        "escalate_network_team",
        "broadcast_status_page",
        "resolve_incident",
    ]
    sla_steps = 12