from __future__ import annotations
from typing import Any, Dict


class IncidentEasyGrader:
    """Grader for easy task: single_service_outage"""
    
    task_id = "incident_easy"
    
    def grade(self, trajectory: list[dict]) -> float:
        """Score an episode trajectory. Returns 0.0 - 1.0"""
        if not trajectory:
            return 0.0
        
        actions = [s.get("action", "") for s in trajectory if s.get("action")]
        resolved = any(s.get("observation", {}).get("incident_resolved", False) for s in trajectory)
        steps = len(trajectory)
        sla = 5  # easy SLA
        
        if not resolved:
            return max(0.0, 0.1 * (len([a for a in actions if a == "rollback_deploy"]) / max(len(actions), 1)))
        
        sla_ok = steps <= sla
        correctness = sum(1 for a in actions if a in ["rollback_deploy", "resolve_incident"]) / 2.0
        
        if sla_ok:
            return round(min(1.0, 0.5 + 0.5 * correctness), 4)
        return round(min(0.6, 0.3 + 0.3 * correctness), 4)


class IncidentMediumGrader:
    """Grader for medium task: dependency_failure"""
    
    task_id = "incident_medium"
    
    def grade(self, trajectory: list[dict]) -> float:
        if not trajectory:
            return 0.0
        
        actions = [s.get("action", "") for s in trajectory if s.get("action")]
        resolved = any(s.get("observation", {}).get("incident_resolved", False) for s in trajectory)
        steps = len(trajectory)
        sla = 8
        
        correct_seq = ["request_logs", "query_dependencies", "escalate_db_team", "restart_service", "resolve_incident"]
        
        if not resolved:
            return max(0.0, 0.1 * (len([a for a in actions if a in correct_seq]) / max(len(correct_seq), 1)))
        
        sla_ok = steps <= sla
        correctness = sum(1 for a in actions if a in correct_seq) / len(correct_seq)
        
        if sla_ok:
            return round(min(1.0, 0.5 + 0.5 * correctness), 4)
        return round(min(0.6, 0.3 + 0.3 * correctness), 4)


class IncidentHardGrader:
    """Grader for hard task: multi_service_root_cause"""
    
    task_id = "incident_hard"
    
    def grade(self, trajectory: list[dict]) -> float:
        if not trajectory:
            return 0.0
        
        actions = [s.get("action", "") for s in trajectory if s.get("action")]
        resolved = any(s.get("observation", {}).get("incident_resolved", False) for s in trajectory)
        steps = len(trajectory)
        sla = 12
        
        correct_seq = ["query_region_health", "query_dns_status", "escalate_network_team", "broadcast_status_page", "resolve_incident"]
        
        if not resolved:
            return max(0.0, 0.1 * (len([a for a in actions if a in correct_seq]) / max(len(correct_seq), 1)))
        
        sla_ok = steps <= sla
        correctness = sum(1 for a in actions if a in correct_seq) / len(correct_seq)
        
        if sla_ok:
            return round(min(1.0, 0.5 + 0.5 * correctness), 4)
        return round(min(0.6, 0.3 + 0.3 * correctness), 4)