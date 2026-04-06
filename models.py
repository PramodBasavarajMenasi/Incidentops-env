# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.



"""
Data models for the Incidentops Env Environment.
The incidentops_env environment is a simple test environment that echoes back messages.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import Field

class IncidentopsAction(Action):
    action: str = Field(..., description="Incident response action to execute")

class IncidentopsObservation(Observation):
    alert_summary: str = Field(default="", description="Human-readable incident summary")
    severity: str = Field(default="low", description="Incident severity")
    likely_cause: str = Field(default="unknown", description="Current hypothesis for the root cause")
    hf_confidence: float = Field(default=0.0, description="Confidence score from the parsing model")
    services_affected: List[str] = Field(default_factory=list, description="Affected services")
    logs_available: bool = Field(default=False, description="Whether logs are available")
    log_snippet: str = Field(default="", description="Short evidence snippet")
    service_healthy: bool = Field(default=False, description="Whether service is healthy")
    elapsed_steps: int = Field(default=0, description="Steps since reset")
    sla_steps_remaining: int = Field(default=0, description="Steps remaining before SLA breach")
    action_history: List[str] = Field(default_factory=list, description="Actions taken so far")
    available_actions: List[str] = Field(default_factory=list, description="Available actions")
    incident_resolved: bool = Field(default=False, description="Whether the incident is resolved")
    wrong_escalations: int = Field(default=0, description="Count of wrong team escalations")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extra debug metadata")
    reward: float = Field(default=0.0, description="Reward returned by the last step")
    done: bool = Field(default=False, description="Whether the episode is finished")



