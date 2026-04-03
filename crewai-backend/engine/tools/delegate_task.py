"""
Delegate task tool — assigns a task to a named agent and records it in SharedMemory.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from crewai.tools import tool
from engine.memory.store import SharedMemory

logger = logging.getLogger(__name__)


@tool("delegate_task")
def delegate_task_tool(task_description: str, agent_id: str) -> str:
    """Delegate a task to a specific agent. Args: task_description, agent_id."""
    if not task_description or not task_description.strip():
        return "Error: task_description must be a non-empty string"
    if not agent_id or not agent_id.strip():
        return "Error: agent_id must be a non-empty string"

    ts_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    key = f"delegation:{agent_id}:{ts_ms}"

    try:
        memory = SharedMemory()
        memory.write(
            key=key,
            value=task_description,
            source_agent="ceo",
            collection="work_in_progress",
        )
    except Exception as e:
        logger.warning("delegate_task: memory write failed for key %s: %s", key, e)

    return f"Task delegated to {agent_id}: {task_description}"
