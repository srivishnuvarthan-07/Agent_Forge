from backend.state.store import StateStore, AgentState
from backend.websocket.emitter import EventEmitter
from backend.websocket.events import (
    AGENT_STARTED, AGENT_THINKING, AGENT_COMPLETED, AGENT_SPAWNED,
    AGENT_ERROR, MEMORY_UPDATE, CONFLICT_DETECTED, CONFLICT_RESOLVED, CREW_FINISHED,
)


class EngineConnector:
    def __init__(self, state_store: StateStore, event_emitter: EventEmitter):
        self.state_store = state_store
        self.event_emitter = event_emitter

    async def on_agent_started(self, workflow_id: str, agent_id: str, role: str):
        self.state_store.update_agent_status(workflow_id, agent_id, "started")
        await self.event_emitter.emit(workflow_id, AGENT_STARTED,
                                      {"agent_id": agent_id, "role": role})

    async def on_agent_thinking(self, workflow_id: str, agent_id: str, message: str):
        await self.event_emitter.emit(workflow_id, AGENT_THINKING,
                                      {"agent_id": agent_id, "message": message})

    async def on_agent_completed(self, workflow_id: str, agent_id: str, output: str):
        self.state_store.update_agent_status(workflow_id, agent_id, "completed", output=output)
        await self.event_emitter.emit(workflow_id, AGENT_COMPLETED,
                                      {"agent_id": agent_id, "output": output})

    async def on_agent_spawned(self, workflow_id: str, parent_id: str, new_agent: dict):
        agent_state = AgentState(
            id=new_agent.get("id", ""),
            template_id=new_agent.get("template_id", ""),
            status="pending",
        )
        self.state_store.add_agent_to_workflow(workflow_id, agent_state)
        await self.event_emitter.emit(workflow_id, AGENT_SPAWNED,
                                      {"parent_id": parent_id, "new_agent": new_agent})

    async def on_memory_update(self, workflow_id: str, agent_id: str, key: str, value: str):
        self.state_store.update_memory_keys(workflow_id, key)
        await self.event_emitter.emit(workflow_id, MEMORY_UPDATE,
                                      {"agent_id": agent_id, "key": key, "value": value})

    async def on_conflict_detected(self, workflow_id: str, key: str, agents: list, values: list):
        await self.event_emitter.emit(workflow_id, CONFLICT_DETECTED,
                                      {"key": key, "agents": agents, "values": values})

    async def on_conflict_resolved(self, workflow_id: str, key: str,
                                   resolution: str, resolved_by: str):
        await self.event_emitter.emit(workflow_id, CONFLICT_RESOLVED,
                                      {"key": key, "resolution": resolution,
                                       "resolved_by": resolved_by})

    async def on_crew_finished(self, workflow_id: str, final_output: str):
        self.state_store.complete_workflow(workflow_id, final_output)
        await self.event_emitter.emit(workflow_id, CREW_FINISHED,
                                      {"final_output": final_output})

    async def on_agent_error(self, workflow_id: str, agent_id: str, error: str):
        self.state_store.update_agent_status(workflow_id, agent_id, "error", error=error)
        await self.event_emitter.emit(workflow_id, AGENT_ERROR,
                                      {"agent_id": agent_id, "error": error})
