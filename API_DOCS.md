# AgentWeaver API — Member 1 Integration Guide

Base URL: http://localhost:8000
WebSocket: ws://localhost:8000/ws
Interactive docs: http://localhost:8000/docs

---

## Endpoints

### GET /health
Returns server status and template count.

Response:
{
  "status": "ok",
  "templates_loaded": 10
}

---

### GET /api/agent-templates
Returns all 10 agent templates for the frontend sidebar.

Response: Array of AgentTemplate objects
[
  {
    "id": "ceo",
    "display_name": "CEO Agent",
    "role": "Chief Executive Officer",
    "goal": "Delegate tasks and synthesize final output",
    "backstory": "You are a decisive leader who hires specialists",
    "tools": ["spawn_agent", "delegate_task"],
    "authority_level": "executive",
    "color": "#DC2626",
    "max_iterations": 10,
    "allow_delegation": true
  },
  ...
]

Authority levels: "executive" | "manager" | "senior" | "junior"

---

### GET /api/agent-templates/{template_id}
Returns a single template by id.

Path params: template_id — one of: ceo, researcher, analyst, writer, critic, developer, designer, pm, marketing, finance

Response: AgentTemplate object (same schema as above)
Error 404: { "detail": "Template 'x' not found." }

---

### POST /api/crews/execute
Start a crew execution from canvas JSON. Returns job_id immediately (non-blocking).

Request body:
{
  "nodes": [
    { "id": "ceo",        "authority_level": "executive" },
    { "id": "researcher", "authority_level": "junior" },
    { "id": "analyst",    "authority_level": "junior" }
  ],
  "edges": [
    { "source": "ceo", "target": "researcher" },
    { "source": "ceo", "target": "analyst" },
    { "source": "nodeA", "target": "nodeB", "type": "collaborates_with" }
  ],
  "crew_id": "my_job_123",
  "mode": "demo"
}

Fields:
  nodes[].id              — must match a template id
  nodes[].authority_level — "executive" | "manager" | "senior" | "junior"
  edges[].type            — omit for hierarchy edge; "collaborates_with" for peer relationship
  crew_id                 — optional, auto-generated if omitted
  mode                    — "demo" (no LLM, fast) | "live" (real API) | "hybrid" (live + 10s fallback)

Rules:
  - Exactly ONE node must have authority_level="executive" (the root/CEO)
  - All node ids must match registered template ids

Response 202:
{
  "job_id": "my_job_123",
  "status": "queued",
  "mode": "demo"
}

---

### GET /api/crews/{job_id}/status
Poll execution state. Safe to call even if job_id does not exist (returns not_found instead of 404).

Response:
{
  "job_id": "my_job_123",
  "status": "queued | running | paused | completed | failed | cancelled | not_found",
  "mode": "demo",
  "created_at": "2026-03-30T06:47:00.539447+00:00",
  "updated_at": "2026-03-30T06:47:03.201234+00:00",
  "result": "Final crew output string, or null",
  "error": "Error message if failed, or null",
  "event_count": 7,
  "agent_statuses": {
    "ceo": "completed",
    "researcher": "completed",
    "analyst": "running"
  }
}

Polling recommendation: every 1-2 seconds until status is completed | failed | cancelled

---

### GET /api/crews/{job_id}/events
Returns all WebSocket events captured for a job (useful when WS connection is unavailable).

Response:
{
  "job_id": "my_job_123",
  "events": [
    { "type": "agent_started",   "agent_id": "ceo",        "role": "Chief Executive Officer", "timestamp": "..." },
    { "type": "agent_thinking",  "agent_id": "researcher", "message": "Searching...",          "timestamp": "..." },
    { "type": "agent_completed", "agent_id": "researcher", "output": "Market size is $10B",    "timestamp": "..." },
    ...
  ]
}

---

### POST /api/crews/{job_id}/pause
Pause a running job. Agents finish their current step then wait.

Response: { "job_id": "...", "status": "paused" }
Error 400: Job is not running

---

### POST /api/crews/{job_id}/resume
Resume a paused job.

Response: { "job_id": "...", "status": "running" }
Error 400: Job is not paused

---

### POST /api/crews/{job_id}/cancel
Cancel a job immediately. Unblocks paused jobs before cancelling.

Response: { "job_id": "...", "status": "cancelled" }
Error 400: Job already finished

---

### POST /api/demo/startup
Run the full startup builder demo (no LLM required). Completes in ~6 seconds.

Request body:
{
  "input_idea": "AI-powered personal CRM"
}

Response:
{
  "status": "completed",
  "elapsed_s": 5.6,
  "business_plan": "STARTUP BUSINESS PLAN: AI-powered personal CRM\n...",
  "event_counts": {
    "agent_started": 5,
    "agent_thinking": 2,
    "agent_spawned": 4,
    "memory_update": 15,
    "agent_completed": 5,
    "conflict_detected": 1,
    "conflict_resolved": 1,
    "crew_finished": 1
  },
  "total_events": 34
}

---

## WebSocket Events

Connect to: ws://localhost:8000/ws
Send any text to keep connection alive.
All events include a "timestamp" field (ISO 8601 UTC).

Event types and payloads:

agent_started
  { "type": "agent_started", "agent_id": "researcher", "role": "Research Specialist", "timestamp": "..." }

agent_thinking
  { "type": "agent_thinking", "agent_id": "researcher", "message": "Searching for data...", "timestamp": "..." }

agent_completed
  { "type": "agent_completed", "agent_id": "researcher", "output": "Market size is $10B", "timestamp": "..." }

agent_spawned
  { "type": "agent_spawned", "parent_id": "ceo", "new_agent": { "id": "researcher_a1b2c3d4", "role": "...", "position": { "x": 250, "y": 150 } }, "timestamp": "..." }

agent_error
  { "type": "agent_error", "agent_id": "analyst", "error": "LLM timeout", "timestamp": "..." }

memory_update
  { "type": "memory_update", "key": "market_size", "collection": "work_in_progress", "source_agent": "researcher", "timestamp": "..." }

conflict_detected
  { "type": "conflict_detected", "key": "market_size", "agent_a": "researcher", "agent_b": "finance", "severity": "medium", "timestamp": "..." }

conflict_resolved
  { "type": "conflict_resolved", "key": "market_size", "resolved_by": "ceo", "resolution": "Conservative $10B TAM...", "timestamp": "..." }

crew_finished
  { "type": "crew_finished", "crew_id": "my_job_123", "result": "Final business plan...", "timestamp": "..." }

---

## Integration Flow (Member 1 Quickstart)

1. GET /api/agent-templates          — load templates into sidebar
2. User builds canvas (nodes + edges)
3. POST /api/crews/execute           — submit canvas, get job_id
4. Connect ws://localhost:8000/ws    — receive live events
5. Poll GET /api/crews/{job_id}/status every 2s
6. On status=completed, read result field
7. Fallback: GET /api/crews/{job_id}/events if WS unavailable

Canvas rules:
  - node.id must be a valid template id (from step 1)
  - Exactly one node with authority_level="executive"
  - Edges define hierarchy (parent -> child) or collaboration (type: "collaborates_with")

---

## Execution Modes

  demo    No LLM calls. Simulates agent execution with 0.3s delays. ~1-2s total. Use for UI testing.
  live    Real CrewAI + LLM calls. Requires OPENAI_API_KEY env var. 60s per agent, 5min total timeout.
  hybrid  Tries live first (10s timeout), falls back to demo if LLM unavailable.

Set OPENAI_API_KEY environment variable for live/hybrid modes:
  $env:OPENAI_API_KEY = "sk-..."

---

## Memory Collections

Agents share a ChromaDB-backed memory store with 4 collections:

  work_in_progress  Default write target. Confidence 0.0-1.0.
  facts             Requires confidence > 0.9 OR manager_approved=true.
  decisions         CEO/manager resolutions. Written after conflict resolution.
  conflicts         Auto-written when conflict detected between agents.

---

## Error Handling

  Agent failure    — emits agent_error event, execution continues with remaining agents
  Crew timeout     — job status set to "failed", error field contains timeout message
  No executive     — 400: "No executive root node found"
  Multiple roots   — 400: "Expected exactly one executive root, found N: ..."
  Unknown template — 400/404: "Template 'x' not found"