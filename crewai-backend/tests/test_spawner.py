"""
Unit tests for AgentSpawner broadcast behaviour.
Requirements: 7.1, 7.2, 7.4
"""
import sys
import types
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest


# ---------------------------------------------------------------------------
# Stub out the entire heavy import chain BEFORE any engine module is touched.
# This must happen at module level so it runs before pytest collects tests.
# ---------------------------------------------------------------------------
def _stub(name, attrs=None):
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return mod


# crewai — include all names that engine.execution.hierarchy imports
_crewai = _stub("crewai", {
    "Agent": MagicMock(),
    "Task": MagicMock(),
    "Crew": MagicMock(),
    "Process": MagicMock(),
    "LLM": MagicMock(),
})
_stub("crewai.tools", {"tool": lambda f: f})

# chromadb — needs PersistentClient
_chroma_client = MagicMock()
_stub("chromadb", {"PersistentClient": MagicMock(return_value=_chroma_client)})

# other optional deps
for _dep in ("groq", "dotenv", "redis", "pydantic"):
    _stub(_dep)

# Stub the entire engine.templates.registry to break the deep import chain
# (registry → memory.tools → memory.store → chromadb + Python 3.10 syntax)
_registry_mod = _stub("engine.templates.registry", {
    "get_template": MagicMock(),
    "list_templates": MagicMock(return_value=[]),
    "_MEMORY_TOOL_MAP": {},
})

# Also stub engine.websocket.manager and engine.websocket.emitter
_manager_stub = MagicMock()
_manager_stub.queue = []
_stub("engine.websocket.manager", {"manager": _manager_stub})
_emitter_stub = MagicMock()
_stub("engine.websocket.emitter", {"emitter": _emitter_stub, "EventEmitter": MagicMock()})

# Stub engine.memory.crew_memory to avoid pulling in chromadb via store.py
_stub("engine.memory.crew_memory", {"CrewMemoryManager": MagicMock()})


# ---------------------------------------------------------------------------
# Now it's safe to import the module under test
# ---------------------------------------------------------------------------
import engine.execution.spawner as spawner_mod  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_nodes(parent_id: str) -> list[dict]:
    return [{"id": parent_id, "position": {"x": 0, "y": 0}}]


def _make_template():
    t = MagicMock()
    t.authority_level = "worker"
    t.display_name = "Test Agent"
    t.color = "#fff"
    t.role = "role"
    t.goal = "goal"
    t.backstory = "backstory"
    return t


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_spawn_agent_calls_broadcast():
    """asyncio.ensure_future is called with a manager.broadcast coroutine."""
    mock_manager = MagicMock()
    mock_emitter = MagicMock()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_manager.broadcast.return_value = AsyncMock()()

    with patch.object(spawner_mod, "get_template", return_value=_make_template()), \
         patch.object(spawner_mod, "manager", mock_manager), \
         patch.object(spawner_mod, "emitter", mock_emitter), \
         patch.object(spawner_mod.asyncio, "get_event_loop", return_value=mock_loop), \
         patch.object(spawner_mod.asyncio, "ensure_future") as mock_ensure_future:

        spawner = spawner_mod.AgentSpawner()
        spawner.spawn_agent("analyst", "parent_1", "do something", _make_nodes("parent_1"))

    mock_ensure_future.assert_called_once()
    mock_manager.broadcast.assert_called_once()
    event_arg = mock_manager.broadcast.call_args[0][0]
    assert event_arg["type"] == "agent_spawned"
    assert event_arg["parent_id"] == "parent_1"


def test_spawn_agent_calls_emitter_agent_spawned():
    """emitter.agent_spawned is called with the correct parent_id and node."""
    mock_manager = MagicMock()
    mock_emitter = MagicMock()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_manager.broadcast.return_value = AsyncMock()()

    with patch.object(spawner_mod, "get_template", return_value=_make_template()), \
         patch.object(spawner_mod, "manager", mock_manager), \
         patch.object(spawner_mod, "emitter", mock_emitter), \
         patch.object(spawner_mod.asyncio, "get_event_loop", return_value=mock_loop), \
         patch.object(spawner_mod.asyncio, "ensure_future"):

        spawner = spawner_mod.AgentSpawner()
        spawner.spawn_agent("analyst", "parent_2", "task", _make_nodes("parent_2"))

    mock_emitter.agent_spawned.assert_called_once()
    parent_arg, node_arg = mock_emitter.agent_spawned.call_args[0]
    assert parent_arg == "parent_2"
    assert node_arg["parent_id"] == "parent_2"


def test_spawn_agent_does_not_append_to_queue():
    """manager.queue is not mutated by spawn_agent (no raw event appended as delivery)."""
    mock_manager = MagicMock()
    mock_emitter = MagicMock()
    mock_loop = MagicMock()
    mock_loop.is_running.return_value = True
    mock_manager.broadcast.return_value = AsyncMock()()

    real_queue: list = []
    mock_manager.queue = real_queue

    with patch.object(spawner_mod, "get_template", return_value=_make_template()), \
         patch.object(spawner_mod, "manager", mock_manager), \
         patch.object(spawner_mod, "emitter", mock_emitter), \
         patch.object(spawner_mod.asyncio, "get_event_loop", return_value=mock_loop), \
         patch.object(spawner_mod.asyncio, "ensure_future"):

        spawner = spawner_mod.AgentSpawner()
        spawner.spawn_agent("analyst", "parent_3", "task", _make_nodes("parent_3"))

    assert len(real_queue) == 0, (
        f"Expected queue to be empty but got {real_queue}"
    )
