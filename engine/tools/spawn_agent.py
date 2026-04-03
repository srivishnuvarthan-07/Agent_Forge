"""
Spawn agent tool — queues a spawn request on the running HierarchyEngine,
then falls back to AgentSpawner broadcast if no engine is active.
"""
from __future__ import annotations
from crewai.tools import tool
from engine.execution.spawner import AgentSpawner

# Current crew_id is injected at runtime by HierarchyEngine
_current_crew_id: str | None = None


def set_current_crew_id(crew_id: str | None) -> None:
    global _current_crew_id
    _current_crew_id = crew_id


@tool("spawn_agent")
def spawn_agent_tool(template_id: str, task_description: str, parent_id: str = "ceo") -> str:
    """Spawn a new agent from a template. Args: template_id, task_description, parent_id."""
    # Try to enqueue on the active engine first (end-to-end execution)
    if _current_crew_id:
        try:
            from engine.execution.hierarchy import get_active_engine
            engine = get_active_engine(_current_crew_id)
            if engine:
                queued = engine.enqueue_spawn(template_id, task_description, parent_id)
                if queued:
                    return f"Queued spawn of '{template_id}' agent (crew: {_current_crew_id})"
                else:
                    return f"Error: max spawn depth reached, cannot spawn '{template_id}'"
        except Exception as e:
            return f"Spawn error: {e}"

    # Fallback: broadcast WS event only (no active engine context)
    try:
        spawner = AgentSpawner()
        new_id = spawner.spawn_agent(
            template_id=template_id,
            parent_id=parent_id,
            task_description=task_description,
            current_nodes=[],
        )
        return f"Spawned agent '{new_id}' from template '{template_id}' (broadcast only)"
    except KeyError:
        return f"Error: unknown template '{template_id}'"
    except Exception as e:
        return f"Spawn error: {e}"
