---
title: Incidentops Env Environment Server
emoji: ⏰
colorFrom: yellow
colorTo: blue
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---
# 🚨 IncidentOps-Env

> **OpenEnv-compatible Reinforcement Learning environment for AI-driven incident response**  
> Meta PyTorch Hackathon × Scaler School of Technology — Round 1 Submission

[![Hugging Face Space](https://img.shields.io/badge/🤗%20HuggingFace-Space-blue)](https://huggingface.co/spaces/menasi11/incidentops-env)
[![OpenEnv](https://img.shields.io/badge/OpenEnv-Compatible-green)](https://github.com/openenv)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)](https://fastapi.tiangolo.com)

---

## 📌 Problem Statement

Modern engineering teams face an ever-growing volume of production incidents — SEV-1 outages, cascading service failures, ambiguous alerts with incomplete logs — all under strict SLA pressure. A human on-call engineer must rapidly triage signals, investigate root causes, engage the right teams, and resolve incidents before breach.

**This is exactly the kind of high-stakes sequential decision-making task where AI agents can be trained and evaluated.** Yet, no standardized RL benchmark environment exists for incident response.

**IncidentOps-Env** fills that gap: a realistic, multi-difficulty OpenEnv environment that forces an AI agent to reason under uncertainty, gather evidence, escalate correctly, and resolve production incidents — all within SLA constraints.

---

## 💡 Why This Problem?

- **Real-world complexity**: Incident response is not a game or toy task. It involves ambiguous observations, partial information, and high cost of wrong actions.
- **Sequential decision-making**: Each action (request logs, escalate, rollback) changes the environment state and brings the agent closer to — or further from — resolution.
- **Measurable outcomes**: Success, SLA compliance, wrong escalations, and efficiency are all objectively measurable, making it ideal for RL benchmarking.
- **Practical AI value**: An agent trained on this environment could assist on-call engineers in real SRE workflows.

---

## 🏗️ How It Works

The environment exposes a `step() / reset() / state()` HTTP API via FastAPI, fully compatible with the OpenEnv spec.

```
Agent → POST /reset (task_id) → Initial Observation
Agent → POST /step  (action)  → Observation + Reward + Done
Agent → GET  /grade (task_id) → Final Score [0.0 – 1.0]
```

At each step, the agent receives a structured **observation** (alert summary, severity, affected services, log snippets, confidence scores, action history) and must choose one action from the available action set. The environment tracks whether the agent:

- Gathers evidence before deciding
- Escalates to the **correct** team
- Stays within the SLA step budget
- Resolves the incident with the right sequence of actions

A shaped **reward function** provides dense feedback throughout the episode — not just at the end.

---

## 📋 Tasks

### Task 1 — `incident_easy`: Single Service Outage

| Property | Value |
|---|---|
| Severity | SEV-2 / High |
| Root Cause | Bad deployment → connection pool exhaustion |
| SLA Budget | 5 steps |
| Affected Service | `payment-service` |

**Scenario**: A deployment at 14:32 UTC caused latency spikes on the payment service. Logs are available. The agent must recognize the deployment as the cause and rollback without unnecessary detours.

**Optimal sequence**: `rollback_deploy` → `resolve_incident`

**What the agent must learn**: When logs clearly point to a bad deploy, act fast — don't over-investigate.

---

### Task 2 — `incident_medium`: Dependency Failure

| Property | Value |
|---|---|
| Severity | SEV-1 / Critical |
| Root Cause | Database timeout cascading to multiple services |
| SLA Budget | 8 steps |
| Affected Services | `api-gateway`, `user-profile-service` |

**Scenario**: Multiple services are degraded with no logs initially available. The agent must request logs first, query dependencies to identify the DB as the bottleneck, engage the DB team, and then restart the service.

**Optimal sequence**: `request_logs` → `query_dependencies` → `escalate_db_team` → `restart_service` → `resolve_incident`

**What the agent must learn**: Investigate before escalating. Escalating the wrong team costs heavy reward penalty.

---

### Task 3 — `incident_hard`: Multi-Service Root Cause

| Property | Value |
|---|---|
| Severity | SEV-1 / Critical |
| Root Cause | DNS failure in EU region (ambiguous initial signals) |
| SLA Budget | 12 steps |
| Affected Services | `auth-service`, `payment-service`, `checkout-service` |

**Scenario**: EU checkout is failing across auth, payment, and checkout. Logs are incomplete. The initial `likely_cause` is `ambiguous` with only 55% confidence. The agent must check region health, query DNS status, engage the network team, broadcast a status update, and resolve.

**Optimal sequence**: `query_region_health` → `query_dns_status` → `escalate_network_team` → `broadcast_status_page` → `resolve_incident`

**What the agent must learn**: Under ambiguity, gather the right evidence systematically. Wrong escalations (e.g., DB team for a DNS issue) are penalized. Broadcast early for SEV-1 multi-service incidents.

---

## 🎯 Reward Function

The reward function provides **dense, shaped feedback** across the full episode trajectory:

| Event | Reward |
|---|---|
| Each step taken | `-0.05` (step cost) |
| Duplicate action | `-0.20` |
| Correct rollback (bad deployment) | `+1.0` |
| Correct log request (when unavailable) | `+0.30` |
| Correct dependency query (DB timeout) | `+0.50` |
| Correct DNS query (DNS issue) | `+0.50` |
| Region health check (ambiguous) | `+0.40` |
| Correct team escalation | `+0.70` |
| Wrong team escalation | `-0.50` |
| Resolve within SLA with evidence | `+1.50` |
| Premature resolve | `-1.0` to `-2.0` |
| SLA breach | `-0.50` per excess step |

---

## 📊 Observation Space

```python
class IncidentopsObservation(Observation):
    alert_summary: str          # Human-readable incident description
    severity: str               # "low" | "high" | "critical"
    likely_cause: str           # Current root cause hypothesis
    hf_confidence: float        # Confidence in the hypothesis [0.0–1.0]
    services_affected: List[str]
    logs_available: bool
    log_snippet: str            # Evidence string (if logs available)
    service_healthy: bool
    elapsed_steps: int
    sla_steps_remaining: int
    action_history: List[str]
    available_actions: List[str]
    incident_resolved: bool
    wrong_escalations: int
    reward: float
    done: bool
```

---

## ⚡ Action Space

Actions vary by task. The full set across all tasks:

| Action | Description |
|---|---|
| `request_logs` | Fetch logs for the affected services |
| `query_dependencies` | Check upstream/downstream service dependencies |
| `query_dns_status` | Query DNS resolver status in affected region |
| `query_region_health` | Check regional infrastructure health |
| `rollback_deploy` | Revert the most recent deployment |
| `restart_service` | Restart the affected service(s) |
| `escalate_db_team` | Page the database on-call team |
| `escalate_network_team` | Page the network/infrastructure team |
| `broadcast_status_page` | Post a public status update |
| `resolve_incident` | Mark the incident as resolved |

---

## 🚀 Setup & Usage

### Run Locally

```bash
git clone https://huggingface.co/spaces/menasi11/incidentops-env
cd incidentops-env

pip install -r server/requirements.txt

uvicorn server.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t incidentops-env .
docker run -p 8000:8000 incidentops-env
```

### Run Baseline Inference

```bash
export HF_TOKEN=your_hf_token_here
python inference.py
```

The inference script uses `Qwen/Qwen2.5-72B-Instruct` via the HuggingFace Router with an LLM-first policy and a deterministic fallback. It runs all three tasks and logs per-step rewards and final scores.

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/reset` | Reset environment. Body: `{"task_id": "incident_easy"}` |
| `POST` | `/step` | Take action. Body: `{"action": {"action": "rollback_deploy"}}` |
| `GET` | `/state` | Get current environment state |
| `GET` | `/tasks` | List all available tasks |
| `GET/POST` | `/grade` | Get grader score. Param: `?task_id=incident_easy` |

---

## 📈 Baseline Scores

Scores produced by the LLM baseline agent (`Qwen2.5-72B-Instruct`) on Hugging Face Inference API:

| Task | Score | Success |
|---|---|---|
| `incident_easy` | ~0.80 | ✅ |
| `incident_medium` | ~0.65 | ✅ |
| `incident_hard` | ~0.50 | ⚠️ Partial |

> Scores reflect the combination of resolution success, SLA compliance, correct action selection, and efficiency.

---

## 🗂️ Project Structure

```
incidentops-env/
├── server/
│   ├── app.py                          # FastAPI application + /grade + /tasks endpoints
│   ├── incidentops_env_environment.py  # Core OpenEnv Environment class
│   └── requirements.txt
├── models.py                           # Pydantic Action + Observation types
├── graders.py                          # IncidentEasyGrader, IncidentMediumGrader, IncidentHardGrader
├── client.py                           # OpenEnv EnvClient wrapper
├── inference.py                        # Baseline LLM agent runner
├── openenv.yaml                        # OpenEnv spec metadata
├── Dockerfile
└── README.md
```

---

## 🔧 OpenEnv Compliance

This environment implements the full OpenEnv interface:

- ✅ `reset(task_id)` → returns initial `IncidentopsObservation`
- ✅ `step(action)` → returns `observation, reward, done, info`
- ✅ `state` property → returns current `State`
- ✅ Typed Pydantic models for `Action` and `Observation`
- ✅ `openenv.yaml` with spec version, tasks, and grader config
- ✅ Graders with deterministic `[0.0–1.0]` scoring
- ✅ Deployed to Hugging Face Spaces as a Docker container

---

## 👤 Author

Built solo for the **Meta PyTorch Hackathon × Scaler School of Technology — Round 1**

🤗 Space: [huggingface.co/spaces/menasi11/incidentops-env](https://huggingface.co/spaces/menasi11/incidentops-env)

---

## 📄 License

This project is submitted as part of the OpenEnv Hackathon. Core OpenEnv framework components are copyright Meta Platforms, Inc. and affiliates, licensed under the BSD-style license included in the repository.
