# DEPRECATED: Not the active entry point. Use: uvicorn api.main:app
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from dataclasses import asdict
from pydantic import BaseModel
from engine.templates.registry import get_template, list_templates
from engine.execution.hierarchy import HierarchyEngine
from engine.websocket.manager import manager

app = FastAPI(title="Agent Template API")
engine = HierarchyEngine()


# ── Models ────────────────────────────────────────────────────────────────────

class CanvasPayload(BaseModel):
    nodes: list[dict]
    edges: list[dict]


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

@app.post("/api/crews/execute")
def api_execute_crew(payload: CanvasPayload):
    try:
        result = engine.execute(payload.nodes, payload.edges)
        return {"status": "completed", "result": str(result)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
