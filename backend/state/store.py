from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AgentState(BaseModel):
    id: str
    template_id: str = ""
    status: str = "pending"
    current_task: str = ""
    output: Optional[str] = None
    error: Optional[str] = None


class WorkflowState(BaseModel):
    workflow_id: str
    status: str = "created"
    agents: list[AgentState] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    final_output: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StateStore:
    def __init__(self):
        self.workflows: dict[str, WorkflowState] = {}

    def create_workflow(self, workflow_id: str, initial_nodes: list) -> WorkflowState:
        agents = [
            AgentState(id=n.get("id", str(i)), template_id=n.get("type", ""))
            for i, n in enumerate(initial_nodes)
        ]
        wf = WorkflowState(workflow_id=workflow_id, status="running", agents=agents)
        self.workflows[workflow_id] = wf
        return wf

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        return self.workflows.get(workflow_id)

    def update_agent_status(self, workflow_id: str, agent_id: str, status: str,
                            output: str = None, error: str = None):
        wf = self.workflows.get(workflow_id)
        if not wf:
            return
        for agent in wf.agents:
            if agent.id == agent_id:
                agent.status = status
                if output is not None:
                    agent.output = output
                if error is not None:
                    agent.error = error
                break
        wf.updated_at = datetime.utcnow().isoformat()

    def add_agent_to_workflow(self, workflow_id: str, agent_state: AgentState):
        wf = self.workflows.get(workflow_id)
        if wf:
            wf.agents.append(agent_state)
            wf.updated_at = datetime.utcnow().isoformat()

    def update_memory_keys(self, workflow_id: str, key: str):
        wf = self.workflows.get(workflow_id)
        if wf and key not in wf.memory_keys:
            wf.memory_keys.append(key)
            wf.updated_at = datetime.utcnow().isoformat()

    def complete_workflow(self, workflow_id: str, final_output: str):
        wf = self.workflows.get(workflow_id)
        if wf:
            wf.status = "completed"
            wf.final_output = final_output
            wf.updated_at = datetime.utcnow().isoformat()

    def get_all_workflows(self) -> list[WorkflowState]:
        return list(self.workflows.values())
