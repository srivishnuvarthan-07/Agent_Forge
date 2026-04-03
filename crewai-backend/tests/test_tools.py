"""
Unit tests for all 7 tools in engine/tools/.
Uses sys.modules stubs for heavy deps (crewai, chromadb, etc.) at module level.
"""
from __future__ import annotations
import sys
import types
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Stub heavy dependencies BEFORE any engine module is imported
# ---------------------------------------------------------------------------

def _stub(name: str, attrs: dict | None = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return mod


def _crewai_tool_decorator(name_or_func=None):
    """Handles both @tool and @tool('name') usage."""
    if callable(name_or_func):
        return name_or_func
    return lambda f: f


_stub("crewai", {
    "Agent": MagicMock(),
    "Task": MagicMock(),
    "Crew": MagicMock(),
    "Process": MagicMock(),
    "LLM": MagicMock(),
})
_stub("crewai.tools", {"tool": _crewai_tool_decorator})

_chroma_client = MagicMock()
_stub("chromadb", {"PersistentClient": MagicMock(return_value=_chroma_client)})

for _dep in ("groq", "dotenv", "redis", "pydantic", "duckduckgo_search"):
    _stub(_dep)

_stub("engine.websocket.manager", {"manager": MagicMock()})
_stub("engine.websocket.emitter", {"emitter": MagicMock(), "EventEmitter": MagicMock()})
_stub("engine.memory.crew_memory", {"CrewMemoryManager": MagicMock()})
_stub("engine.templates.registry", {
    "get_template": MagicMock(),
    "list_templates": MagicMock(return_value=[]),
    "_MEMORY_TOOL_MAP": {},
})

# ---------------------------------------------------------------------------
# Now import the tools under test
# ---------------------------------------------------------------------------
from engine.tools.calculator import calculator_tool          # noqa: E402
from engine.tools.web_search import web_search_tool          # noqa: E402
from engine.tools.code_executor import code_executor_tool    # noqa: E402
from engine.tools.file_write import file_write_tool          # noqa: E402
from engine.tools.spawn_agent import spawn_agent_tool        # noqa: E402
from engine.tools.delegate_task import delegate_task_tool    # noqa: E402
from engine.tools.flag_conflict import flag_conflict_tool    # noqa: E402


# ===========================================================================
# calculator
# ===========================================================================

def test_calculator_addition():
    assert calculator_tool("2+3") == "5"


def test_calculator_division():
    assert calculator_tool("10/4") == "2.5"


def test_calculator_floor_div():
    assert calculator_tool("10//3") == "3"


def test_calculator_power():
    assert calculator_tool("2**8") == "256"


def test_calculator_modulo():
    assert calculator_tool("10%3") == "1"


def test_calculator_unary_neg():
    assert calculator_tool("-5") == "-5"


def test_calculator_division_by_zero():
    assert calculator_tool("1/0") == "Error: division by zero"


def test_calculator_disallowed_call():
    result = calculator_tool("abs(-1)")
    assert "disallowed" in result.lower()


def test_calculator_empty():
    assert calculator_tool("") == "Error: expression must be a non-empty string"


def test_calculator_invalid_syntax():
    result = calculator_tool("2+")
    assert "Error" in result


# ===========================================================================
# web_search
# ===========================================================================

def test_web_search_empty_query():
    assert web_search_tool("") == "Error: query must be a non-empty string"


def test_web_search_whitespace_query():
    assert web_search_tool("   ") == "Error: query must be a non-empty string"


def test_web_search_mocked_results():
    fake_results = [
        {"title": "Result One", "href": "https://example.com/1", "body": "Body one"},
        {"title": "Result Two", "href": "https://example.com/2", "body": "Body two"},
    ]
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = fake_results

    with patch("engine.tools.web_search.DDGS", return_value=mock_ddgs):
        result = web_search_tool("python testing")

    assert "Result One" in result
    assert "Result Two" in result


def test_web_search_no_results():
    mock_ddgs = MagicMock()
    mock_ddgs.text.return_value = []

    with patch("engine.tools.web_search.DDGS", return_value=mock_ddgs):
        result = web_search_tool("xyzzy nothing here")

    assert "No results found" in result


def test_web_search_network_error():
    mock_ddgs = MagicMock()
    mock_ddgs.text.side_effect = Exception("network failure")

    with patch("engine.tools.web_search.DDGS", return_value=mock_ddgs):
        result = web_search_tool("some query")

    assert "Search error:" in result


# ===========================================================================
# code_executor
# ===========================================================================

def test_code_executor_empty():
    assert code_executor_tool("") == "Error: no code provided"


def test_code_executor_stdout():
    result = code_executor_tool("print('hello')")
    assert result == "hello"


def test_code_executor_runtime_error():
    result = code_executor_tool("1/0")
    assert result.startswith("Error:")


def test_code_executor_syntax_error():
    result = code_executor_tool("def f(:")
    assert result.startswith("SyntaxError:")


def test_code_executor_restricted_os():
    result = code_executor_tool("import os")
    assert "restricted" in result.lower() or "Error" in result


def test_code_executor_restricted_sys():
    result = code_executor_tool("import sys")
    assert "restricted" in result.lower() or "Error" in result


def test_code_executor_timeout():
    with patch("engine.tools.code_executor.subprocess.run",
               side_effect=subprocess.TimeoutExpired(cmd="python", timeout=10)):
        result = code_executor_tool("while True: pass")
    assert "timed out" in result.lower()


# ===========================================================================
# file_write
# ===========================================================================

def test_file_write_empty_path():
    assert file_write_tool("", "content") == "Error: path must be a non-empty string"


def test_file_write_traversal_blocked():
    result = file_write_tool("../etc/passwd", "data")
    assert "traversal" in result.lower() or "Error" in result


def test_file_write_absolute_blocked():
    result = file_write_tool("/etc/passwd", "data")
    assert "absolute" in result.lower() or "Error" in result


def test_file_write_success(tmp_path):
    import engine.tools.file_write as fw_mod
    original_base = fw_mod.BASE_DIR
    fw_mod.BASE_DIR = tmp_path / "output"
    fw_mod.BASE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        result = file_write_tool("test_output.txt", "hello world")
        assert "Written" in result
        written_file = fw_mod.BASE_DIR / "test_output.txt"
        assert written_file.exists()
    finally:
        fw_mod.BASE_DIR = original_base


# ===========================================================================
# spawn_agent
# ===========================================================================

def test_spawn_agent_unknown_template():
    mock_spawner_instance = MagicMock()
    mock_spawner_instance.spawn_agent.side_effect = KeyError("unknown_template")
    mock_spawner_cls = MagicMock(return_value=mock_spawner_instance)

    with patch("engine.tools.spawn_agent.AgentSpawner", mock_spawner_cls):
        result = spawn_agent_tool("unknown_template", "do something")

    assert "Error: unknown template" in result


def test_spawn_agent_success():
    mock_spawner_instance = MagicMock()
    mock_spawner_instance.spawn_agent.return_value = "analyst_abc123"
    mock_spawner_cls = MagicMock(return_value=mock_spawner_instance)

    with patch("engine.tools.spawn_agent.AgentSpawner", mock_spawner_cls):
        result = spawn_agent_tool("analyst", "analyse the market")

    assert "analyst_abc123" in result


# ===========================================================================
# delegate_task
# ===========================================================================

def test_delegate_task_empty_description():
    result = delegate_task_tool("", "agent_1")
    assert "Error" in result


def test_delegate_task_empty_agent():
    result = delegate_task_tool("do something", "")
    assert "Error" in result


def test_delegate_task_success():
    mock_memory = MagicMock()
    mock_memory_cls = MagicMock(return_value=mock_memory)

    with patch("engine.tools.delegate_task.SharedMemory", mock_memory_cls):
        result = delegate_task_tool("analyse the market", "analyst_1")

    assert "Task delegated to" in result
    assert "analyst_1" in result


def test_delegate_task_memory_failure():
    mock_memory = MagicMock()
    mock_memory.write.side_effect = Exception("chroma down")
    mock_memory_cls = MagicMock(return_value=mock_memory)

    with patch("engine.tools.delegate_task.SharedMemory", mock_memory_cls):
        result = delegate_task_tool("analyse the market", "analyst_1")

    # Should still return confirmation even when memory write fails
    assert "Task delegated to" in result
    assert "analyst_1" in result


# ===========================================================================
# flag_conflict
# ===========================================================================

def test_flag_conflict_empty_key():
    result = flag_conflict_tool("", "some reason")
    assert "Error" in result


def test_flag_conflict_empty_reason():
    result = flag_conflict_tool("some_key", "")
    assert "Error" in result


def test_flag_conflict_success():
    mock_memory = MagicMock()
    mock_memory_cls = MagicMock(return_value=mock_memory)

    with patch("engine.tools.flag_conflict.SharedMemory", mock_memory_cls):
        result = flag_conflict_tool("budget_2024", "values conflict")

    assert "Conflict flagged for key" in result
    assert "budget_2024" in result
