import asyncio
import uuid
from fastapi import APIRouter, Request

demo_router = APIRouter()


@demo_router.post("/demo/startup")
async def demo_startup(request: Request):
    engine_connector = request.app.state.engine_connector
    state_store = request.app.state.state_store

    workflow_id = str(uuid.uuid4())
    state_store.create_workflow(workflow_id, [
        {"id": "ceo", "type": "ceo_agent"},
        {"id": "dev", "type": "dev_agent"},
        {"id": "qa", "type": "qa_agent"},
        {"id": "pm", "type": "pm_agent"},
    ])

    async def run_demo():
        await engine_connector.on_agent_started(workflow_id, "ceo", "CEO")
        await asyncio.sleep(1)
        await engine_connector.on_agent_thinking(workflow_id, "ceo", "Analyzing project scope...")
        await asyncio.sleep(1)

        for agent_id, role in [("dev", "Developer"), ("qa", "QA"), ("pm", "PM")]:
            await engine_connector.on_agent_spawned(workflow_id, "ceo",
                                                    {"id": agent_id, "template_id": role})
            await engine_connector.on_agent_started(workflow_id, agent_id, role)
            await asyncio.sleep(0.5)

        await engine_connector.on_conflict_detected(workflow_id, "priority",
                                                    ["dev", "pm"], ["speed", "quality"])
        await asyncio.sleep(1)
        await engine_connector.on_conflict_resolved(workflow_id, "priority",
                                                    "balance speed and quality", "ceo")

        for agent_id in ["dev", "qa", "pm"]:
            await engine_connector.on_agent_completed(workflow_id, agent_id,
                                                      f"{agent_id} task done")
            await asyncio.sleep(0.3)

        await engine_connector.on_crew_finished(workflow_id, "Project delivered successfully")

    asyncio.create_task(run_demo())
    return {"workflow_id": workflow_id, "demo": "running"}
