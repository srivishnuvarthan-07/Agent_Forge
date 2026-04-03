from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from backend.websocket.events import SYSTEM_STATUS

router = APIRouter()


class ExecuteBody(BaseModel):
    workflow_id: str
    nodes: list = []
    edges: list = []
    mode: Optional[str] = "auto"


@router.post("/crews/execute")
async def execute_crew(body: ExecuteBody, request: Request):
    state_store = request.app.state.state_store
    emitter = request.app.state.emitter

    if state_store.get_workflow(body.workflow_id):
        raise HTTPException(status_code=400, detail="workflow_id already exists")

    state_store.create_workflow(body.workflow_id, body.nodes)
    await emitter.emit(body.workflow_id, SYSTEM_STATUS,
                       {"message": "Workflow created, starting execution"})
    return {"job_id": body.workflow_id, "status": "started"}


@router.get("/crews/{workflow_id}/status")
async def get_status(workflow_id: str, request: Request):
    state_store = request.app.state.state_store
    wf = state_store.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf


@router.post("/crews/{workflow_id}/pause")
async def pause_crew(workflow_id: str, request: Request):
    state_store = request.app.state.state_store
    emitter = request.app.state.emitter
    wf = state_store.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.status = "paused"
    await emitter.emit(workflow_id, SYSTEM_STATUS, {"message": "Workflow paused"})
    return {"status": "paused"}


@router.post("/crews/{workflow_id}/resume")
async def resume_crew(workflow_id: str, request: Request):
    state_store = request.app.state.state_store
    emitter = request.app.state.emitter
    wf = state_store.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.status = "running"
    await emitter.emit(workflow_id, SYSTEM_STATUS, {"message": "Workflow resumed"})
    return {"status": "running"}


@router.post("/crews/{workflow_id}/cancel")
async def cancel_crew(workflow_id: str, request: Request):
    state_store = request.app.state.state_store
    emitter = request.app.state.emitter
    wf = state_store.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf.status = "cancelled"
    await emitter.emit(workflow_id, SYSTEM_STATUS, {"message": "Workflow cancelled"})
    return {"status": "cancelled"}


@router.get("/crews")
async def list_crews(request: Request):
    state_store = request.app.state.state_store
    return state_store.get_all_workflows()


@router.get("/health")
async def health(request: Request):
    state_store = request.app.state.state_store
    return {"status": "ok", "active_workflows": len(state_store.workflows)}
