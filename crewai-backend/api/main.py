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
    """Demo mode: simulate execution with cached responses, no LLM calls."""
    _update_job(job_id, status="running")
    snapshot = len(emitter.log)
    try:
        agent_ids = [n["id"] for n in nodes]
        for aid in agent_ids:
            if _cancel_flags.get(job_id, threading.Event()).is_set():
                _update_job(job_id, status="cancelled")
                return
            while _pause_flags.get(job_id, threading.Event()).is_set():
                time.sleep(0.2)
            current = (get_job(job_id) or {}).get("agent_statuses", {})
            _update_job(job_id, agent_statuses={**current, aid: "running"})
            emitter.agent_started(aid, aid)
            time.sleep(0.3)
            emitter.agent_completed(aid, f"[demo] {aid} completed task.")
            current = (get_job(job_id) or {}).get("agent_statuses", {})
            _update_job(job_id, agent_statuses={**current, aid: "completed"})
        result = "[demo] All agents completed. Business plan synthesized."
        emitter.crew_finished(job_id, result)
        _update_job(job_id, status="completed", result=result, events=emitter.log[snapshot:])
    except Exception as e:
        emitter.agent_error("crew", str(e))
        _update_job(job_id, status="failed", error=str(e))


def _run_live_mode(job_id, nodes, edges, timeout=CREW_TIMEOUT):
    """Live mode: real CrewAI + LLM calls with per-agent error isolation."""
    _update_job(job_id, status="running")
    snapshot = len(emitter.log)

    # ── Live state listener ───────────────────────────────────────────────────
    def _on_event(event: dict):
        """Update job agent_statuses from engine events in real time."""
        etype = event.get("type", "")
        agent_id = event.get("agent_id", "")
        if not agent_id:
            return
        current = (get_job(job_id) or {}).get("agent_statuses", {})
        if etype == "agent_started":
            update_job(job_id, agent_statuses={**current, agent_id: "running"})
        elif etype == "agent_completed":
            update_job(job_id, agent_statuses={**current, agent_id: "completed"})
        elif etype == "agent_error":
            update_job(job_id, agent_statuses={**current, agent_id: "error"})

    emitter.subscribe(_on_event)
    try:
        engine = HierarchyEngine(event_emitter=emitter)

        # agent lifecycle events handled via step_callback in HierarchyEngine.instantiate_agent

        result_holder = [None]
        error_holder  = [None]

        def _target():
            try:
                result_holder[0] = engine.execute(nodes, edges, crew_id=job_id)
            except Exception as e:
                error_holder[0] = str(e)

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            _update_job(job_id, status="failed", error=f"Crew timed out after {timeout}s")
            return

        if error_holder[0]:
            _update_job(job_id, status="failed", error=error_holder[0], events=emitter.log[snapshot:])
        else:
            _update_job(job_id, status="completed", result=str(result_holder[0]), events=emitter.log[snapshot:])

    except Exception as e:
        _update_job(job_id, status="failed", error=str(e))
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