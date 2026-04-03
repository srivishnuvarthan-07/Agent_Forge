from __future__ import annotations

import config  # Load env vars before any CrewAI imports
import threading
import time
import os
from uuid import uuid4

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, fall back to env vars
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dataclasses import asdict
from pydantic import BaseModel

from engine.templates.registry import get_template, list_templates
from engine.memory.conflict_detector import get_conflicts_for_resolution, resolve_conflict
from engine.execution.hierarchy import HierarchyEngine
from engine.websocket.manager import manager
from engine.websocket.emitter import emitter
from api.job_store import create_job, get_job, update_job, list_jobs

app = FastAPI(title="AgentWeaver API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Job store (SQLite-backed) ─────────────────────────────────────────────────

_job_threads: dict[str, threading.Thread] = {}
_cancel_flags: dict[str, threading.Event] = {}
_pause_flags: dict[str, threading.Event] = {}

AGENT_TIMEOUT = 60       # seconds per agent
CREW_TIMEOUT  = 300      # 5 minutes total


def _update_job(job_id, **kwargs):
    update_job(job_id, **kwargs)

# ── Execution modes ───────────────────────────────────────────────────────────

def _run_demo_mode(job_id, nodes, edges):
    """Demo mode: simulate execution, broadcasting events in frontend-compatible format."""
    _update_job(job_id, status="running")
    snapshot = len(emitter.log)

    AGENT_META = {
        "prompt":    {"label": "User Prompt",    "icon": "💬"},
        "planner":   {"label": "Planner Agent",  "icon": "🗂️"},
        "research":  {"label": "Research Agent", "icon": "🔍"},
        "execution": {"label": "Execution Agent","icon": "⚙️"},
        "summary":   {"label": "Summary Agent",  "icon": "📋"},
    }
    DEMO_OUTPUTS = {
        "prompt":    "Task received and queued for processing.",
        "planner":   "1. Analyse the problem\n2. Research key areas\n3. Execute strategy\n4. Summarise findings",
        "research":  "Found 4 relevant data points:\n• Market size: $2.4B\n• Growth rate: 18% YoY\n• Key players identified\n• Opportunity gap confirmed",
        "execution": "Strategy executed:\n• Drafted action plan\n• Allocated resources\n• Initiated outreach\n• Tracked KPIs",
        "summary":   "Summary: Task completed successfully. All agents contributed structured outputs. Final report is ready for review.",
    }

    try:
        # Broadcast job started
        emitter.emit("job_started", {"jobId": job_id, "prompt": job_id})

        outputs = {}
        agent_ids = [n["id"] for n in nodes]

        for aid in agent_ids:
            if _cancel_flags.get(job_id, threading.Event()).is_set():
                _update_job(job_id, status="cancelled")
                return
            while _pause_flags.get(job_id, threading.Event()).is_set():
                time.sleep(0.2)

            meta = AGENT_META.get(aid, {"label": aid, "icon": "🤖"})
            current = (get_job(job_id) or {}).get("agent_statuses", {})
            _update_job(job_id, agent_statuses={**current, aid: "running"})

            emitter.emit("agent_started", {
                "jobId": job_id,
                "agentId": aid,
                "label": meta["label"],
                "log": f"{meta['icon']} {meta['label']} running...",
            })
            time.sleep(1.0)

            output = DEMO_OUTPUTS.get(aid, f"[demo] {aid} completed.")
            outputs[aid] = output
            current = (get_job(job_id) or {}).get("agent_statuses", {})
            _update_job(job_id, agent_statuses={**current, aid: "completed"})

            emitter.emit("agent_completed", {
                "jobId": job_id,
                "agentId": aid,
                "label": meta["label"],
                "output": output,
                "log": f"✓ {meta['label']} completed",
            })

        result = outputs.get("summary", "[demo] All agents completed.")
        emitter.emit("crew_finished", {
            "jobId": job_id,
            "result": result,
            "outputs": outputs,
            "log": "✅ All agents completed. Report ready.",
        })
        _update_job(job_id, status="completed", result=result, events=emitter.log[snapshot:])

    except Exception as e:
        emitter.agent_error("crew", str(e))
        _update_job(job_id, status="failed", error=str(e))


def _run_live_mode(job_id, nodes, edges, timeout=CREW_TIMEOUT):
    """Live mode: real CrewAI + Groq LLM calls, broadcasts frontend-compatible WS events."""
    _update_job(job_id, status="running")
    snapshot = len(emitter.log)

    # Build a label map from node id → display name for WS events
    label_map = {n["id"]: n.get("label", n["id"]) for n in nodes}

    def _on_event(event: dict):
        """Translate engine events → frontend-compatible format and update job store."""
        etype = event.get("type", "")
        agent_id = event.get("agent_id", "")
        if not agent_id:
            return
        label = label_map.get(agent_id, agent_id)
        current = (get_job(job_id) or {}).get("agent_statuses", {})
        if etype == "agent_started":
            update_job(job_id, agent_statuses={**current, agent_id: "running"})
            emitter.emit("agent_started", {
                "jobId": job_id,
                "agentId": agent_id,
                "label": label,
                "log": f"⚡ {label} is working...",
            })
        elif etype == "agent_completed":
            update_job(job_id, agent_statuses={**current, agent_id: "completed"})
            emitter.emit("agent_completed", {
                "jobId": job_id,
                "agentId": agent_id,
                "label": label,
                "output": event.get("output", ""),
                "log": f"✓ {label} completed",
            })
        elif etype == "agent_error":
            update_job(job_id, agent_statuses={**current, agent_id: "error"})

    emitter.subscribe(_on_event)
    try:
        engine = HierarchyEngine(event_emitter=emitter)
        result_holder = [None]
        error_holder  = [None]

        def _target():
            try:
                result_holder[0] = engine.execute(nodes, edges, crew_id=job_id)
            except Exception as e:
                error_holder[0] = str(e)

        emitter.emit("job_started", {"jobId": job_id})
        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            err = f"Crew timed out after {timeout}s"
            _update_job(job_id, status="failed", error=err)
            emitter.emit("error", {"jobId": job_id, "message": err})
            return

        if error_holder[0]:
            _update_job(job_id, status="failed", error=error_holder[0], events=emitter.log[snapshot:])
            emitter.emit("error", {"jobId": job_id, "message": error_holder[0]})
        else:
            result_str = str(result_holder[0])
            job = get_job(job_id)
            outputs = job.get("agent_statuses", {}) if job else {}
            _update_job(job_id, status="completed", result=result_str, events=emitter.log[snapshot:])
            emitter.emit("crew_finished", {
                "jobId": job_id,
                "result": result_str,
                "outputs": {aid: result_str for aid in label_map},
                "log": "✅ All agents completed. Report ready.",
            })

    except Exception as e:
        _update_job(job_id, status="failed", error=str(e))
        emitter.emit("error", {"jobId": job_id, "message": str(e)})
    finally:
        emitter.unsubscribe(_on_event)


def _run_hybrid_mode(job_id, nodes, edges):
    """Hybrid: live calls with 10s per-agent timeout, falls back to demo output."""
    _run_live_mode(job_id, nodes, edges, timeout=10)
    job = get_job(job_id)
    if job and job["status"] == "failed":
        _update_job(job_id, status="running", error=None)
        _run_demo_mode(job_id, nodes, edges)


def _dispatch(job_id, nodes, edges, mode):
    _cancel_flags[job_id] = threading.Event()
    _pause_flags[job_id]  = threading.Event()
    if mode == "demo":
        _run_demo_mode(job_id, nodes, edges)
    elif mode == "hybrid":
        _run_hybrid_mode(job_id, nodes, edges)
    else:
        _run_live_mode(job_id, nodes, edges)

# ── Models ────────────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    crew_id: str | None = None
    mode: Literal["live", "demo", "hybrid"] = "demo"


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "templates_loaded": len(list_templates())}


# ── Agent Templates ───────────────────────────────────────────────────────────

@app.get("/api/agent-templates")
def api_list_templates():
    return [asdict(t) for t in list_templates()]


@app.get("/api/agent-templates/{template_id}")
def api_get_template(template_id: str):
    try:
        return asdict(get_template(template_id))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Crew Execution ────────────────────────────────────────────────────────────

@app.post("/api/crews/execute", status_code=202)
def api_execute_crew(payload: ExecuteRequest, background_tasks: BackgroundTasks):
    job_id = payload.crew_id or f"job_{uuid4().hex[:8]}"
    create_job(job_id, payload.mode)
    background_tasks.add_task(_dispatch, job_id, payload.nodes, payload.edges, payload.mode)
    return {"job_id": job_id, "status": "queued", "mode": payload.mode}


@app.get("/api/crews/{job_id}/status")
def api_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {
        "job_id":         job["job_id"],
        "status":         job["status"],
        "mode":           job["mode"],
        "created_at":     job["created_at"],
        "updated_at":     job["updated_at"],
        "result":         job["result"],
        "error":          job["error"],
        "event_count":    len(job["events"]),
        "agent_statuses": job["agent_statuses"],
    }


@app.get("/api/crews/{job_id}/events")
def api_job_events(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"job_id": job_id, "events": job["events"]}


@app.post("/api/crews/{job_id}/pause")
def api_pause_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] != "running":
        raise HTTPException(status_code=400, detail="Job is not running.")
    _pause_flags.setdefault(job_id, threading.Event()).set()
    _update_job(job_id, status="paused")
    return {"job_id": job_id, "status": "paused"}


@app.post("/api/crews/{job_id}/resume")
def api_resume_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] != "paused":
        raise HTTPException(status_code=400, detail="Job is not paused.")
    _pause_flags.get(job_id, threading.Event()).clear()
    _update_job(job_id, status="running")
    return {"job_id": job_id, "status": "running"}


@app.post("/api/crews/{job_id}/cancel")
def api_cancel_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    if job["status"] in ("completed", "failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Job already finished.")
    _cancel_flags.setdefault(job_id, threading.Event()).set()
    _pause_flags.get(job_id, threading.Event()).clear()
    _update_job(job_id, status="cancelled")
    emitter.emit("agent_error", {"agent_id": "crew", "error": "Job cancelled by user."})
    return {"job_id": job_id, "status": "cancelled"}


@app.get("/api/crews")
def api_list_jobs():
    jobs = list_jobs()
    return [{"job_id": j["job_id"], "status": j["status"], "mode": j["mode"],
             "created_at": j["created_at"], "updated_at": j["updated_at"]} for j in jobs]


# ── Conflicts ─────────────────────────────────────────────────────────────────

@app.get("/api/conflicts")
def api_list_conflicts():
    return get_conflicts_for_resolution("system")


class ResolveConflictBody(BaseModel):
    resolution: str
    resolved_by: str


@app.post("/api/conflicts/{key}/resolve")
def api_resolve_conflict(key: str, body: ResolveConflictBody):
    try:
        result = resolve_conflict(key, body.resolution, body.resolved_by)
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Conflict '{key}' not found.")


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)