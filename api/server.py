import asyncio, json
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="AgentForge API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_connections = []
_jobs = {}

STEPS = [
    {"id": "prompt",    "label": "User Prompt",  "delay": 0.8},
    {"id": "planner",   "label": "Planner",      "delay": 1.5},
    {"id": "research",  "label": "Research",     "delay": 2.0},
    {"id": "execution", "label": "Execution",    "delay": 1.8},
    {"id": "summary",   "label": "Summary",      "delay": 1.0},
]
OUTPUTS = {
    "prompt":    lambda t: '"' + t + '"',
    "planner":   lambda _: "Breaking task into sub-goals",
    "research":  lambda _: "Gathered 4 relevant sources",
    "execution": lambda _: "Code executed successfully",
    "summary":   lambda _: "Final report ready",
}

async def broadcast(msg):
    text = json.dumps(msg)
    dead = []
    for ws in list(_connections):
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _connections:
            _connections.remove(ws)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _connections:
            _connections.remove(websocket)

async def run_job(job_id, task):
    _jobs[job_id]["status"] = "running"
    await broadcast({"type": "job_started", "job_id": job_id})
    for step in STEPS:
        await asyncio.sleep(step["delay"])
        _jobs[job_id]["agent_statuses"][step["id"]] = "running"
        await broadcast({"type": "agent_started", "job_id": job_id, "agent_id": step["id"], "label": step["label"]})
        await asyncio.sleep(step["delay"])
        out = OUTPUTS[step["id"]](task)
        _jobs[job_id]["agent_statuses"][step["id"]] = "completed"
        _jobs[job_id]["outputs"][step["id"]] = out
        await broadcast({"type": "agent_completed", "job_id": job_id, "agent_id": step["id"], "output": out})
    _jobs[job_id]["status"] = "completed"
    _jobs[job_id]["result"] = _jobs[job_id]["outputs"].get("summary", "Done")
    await broadcast({"type": "crew_finished", "job_id": job_id, "result": _jobs[job_id]["result"]})

class ExecuteRequest(BaseModel):
    task: str
    mode: str = "demo"
    crew_id: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "connections": len(_connections), "jobs": len(_jobs)}

@app.post("/api/crews/execute", status_code=202)
async def execute(payload: ExecuteRequest, background_tasks: BackgroundTasks):
    job_id = payload.crew_id or f"job_{uuid4().hex[:8]}"
    _jobs[job_id] = {"job_id": job_id, "task": payload.task, "status": "queued",
                     "created_at": datetime.now(timezone.utc).isoformat(),
                     "agent_statuses": {}, "outputs": {}, "result": None}
    background_tasks.add_task(run_job, job_id, payload.task)
    return {"job_id": job_id, "status": "queued"}

@app.get("/api/crews/{job_id}/status")
def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, detail=f"Job not found")
    return job

@app.get("/api/crews")
def list_jobs():
    return list(_jobs.values())

@app.get("/api/agent-templates")
def templates():
    return [
        {"id": "planner",   "display_name": "Planner Agent",   "color": "#6366f1"},
        {"id": "research",  "display_name": "Research Agent",  "color": "#0891b2"},
        {"id": "execution", "display_name": "Execution Agent", "color": "#059669"},
        {"id": "summary",   "display_name": "Summary Agent",   "color": "#d97706"},
    ]
