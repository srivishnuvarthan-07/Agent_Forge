"""
Property-based tests for AgentForge engine tools.
Uses Hypothesis for fuzz coverage.

Properties:
  1. calculator idempotence
  2. calculator model-based correctness
  3. file_write round-trip
  4. file_write path safety
  5. all tools return str

Feature: engine-real-tools
"""
from __future__ import annotations
import sys
import types
import os
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Stub heavy deps before any engine import
# ---------------------------------------------------------------------------
def _stub(name, attrs=None):
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules.setdefault(name, mod)
    return mod

def _crewai_tool(name_or_func=None):
    if callable(name_or_func):
        return name_or_func
    return lambda f: f

_stub("crewai", {"Agent": MagicMock(), "Task": MagicMock(), "Crew": MagicMock(),
                  "Process": MagicMock(), "LLM": MagicMock()})
_stub("crewai.tools", {"tool": _crewai_tool})
_stub("chromadb", {"PersistentClient": MagicMock(return_value=MagicMock())})
for _d in ("groq", "dotenv", "redis", "pydantic", "duckduckgo_search"):
    _stub(_d)
_stub("engine.websocket.manager", {"manager": MagicMock()})
_stub("engine.websocket.emitter", {"emitter": MagicMock(), "EventEmitter": MagicMock()})
_stub("engine.memory.crew_memory", {"CrewMemoryManager": MagicMock()})
_stub("engine.templates.registry", {
    "get_template": MagicMock(), "list_templates": MagicMock(return_value=[]),
    "_MEMORY_TOOL_MAP": {},
})
_stub("engine.execution.spawner", {"AgentSpawner": MagicMock()})

from engine.tools.calculator import calculator_tool   # noqa: E402
from engine.tools.file_write import file_write_tool   # noqa: E402
import engine.tools.file_write as fw_mod              # noqa: E402
import tempfile                                        # noqa: E402

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False
    # Create no-op stubs so module-level decorators don't crash
    def given(*a, **kw):
        return lambda f: pytest.mark.skip(reason="hypothesis not installed")(f)
    def settings(*a, **kw):
        return lambda f: f
    def assume(x):
        pass
    class st:  # type: ignore[no-redef]
        @staticmethod
        def text(**kw): return None
        @staticmethod
        def integers(**kw): return None
        @staticmethod
        def sampled_from(x): return None
        @staticmethod
        def one_of(*a): return None
        @staticmethod
        def just(x): return None
        @staticmethod
        def builds(f, *a, **kw): return None
        @staticmethod
        def lists(*a, **kw): return None
        @staticmethod
        def characters(**kw): return None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_eval(expr: str):
    """Reference evaluator using Python's eval on numeric-only expressions."""
    return eval(expr, {"__builtins__": {}})  # noqa: S307


def _is_safe_expr(expr: str) -> bool:
    """True if expr contains only digits, spaces, and safe operators."""
    import re
    return bool(re.fullmatch(r"[\d\s\+\-\*\/\(\)\.]+", expr))


# ---------------------------------------------------------------------------
# Property 1: calculator idempotence
# Feature: engine-real-tools, Property 1: calculator idempotence
# ---------------------------------------------------------------------------
@given(st.text(min_size=1, max_size=30, alphabet=st.characters(blacklist_characters="\x00")))
@settings(max_examples=100)
def test_calculator_idempotence(expr):
    """Evaluating the same expression twice always returns the same result."""
    r1 = calculator_tool(expr)
    r2 = calculator_tool(expr)
    assert r1 == r2, f"Non-idempotent: '{expr}' → '{r1}' then '{r2}'"


# ---------------------------------------------------------------------------
# Property 2: calculator model-based correctness
# Feature: engine-real-tools, Property 2: calculator model-based correctness
# ---------------------------------------------------------------------------
@given(
    a=st.integers(min_value=-1000, max_value=1000),
    b=st.integers(min_value=-1000, max_value=1000),
    op=st.sampled_from(["+", "-", "*"]),
)
@settings(max_examples=100)
def test_calculator_model_based(a, b, op):
    """For safe integer expressions, calculator matches Python's eval."""
    expr = f"{a}{op}{b}"
    expected = str(_safe_eval(expr))
    result = calculator_tool(expr)
    assert result == expected, f"calculator('{expr}') = '{result}', expected '{expected}'"


# ---------------------------------------------------------------------------
# Property 3: file_write round-trip
# Feature: engine-real-tools, Property 3: file_write round-trip
# ---------------------------------------------------------------------------
@given(
    filename=st.text(
        alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_-."),
        min_size=1, max_size=30,
    ),
    content=st.text(min_size=0, max_size=500),
)
@settings(max_examples=50)
def test_file_write_round_trip(filename, content):
    """Writing then reading a file returns the exact same bytes."""
    assume(filename.strip())
    with tempfile.TemporaryDirectory() as tmpdir:
        from pathlib import Path
        original_base = fw_mod.BASE_DIR
        fw_mod.BASE_DIR = Path(tmpdir) / "output"
        fw_mod.BASE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            result = file_write_tool(filename, content)
            if result.startswith("Error") or result.startswith("Write error"):
                return
            written_file = fw_mod.BASE_DIR / filename
            assert written_file.exists()
            assert written_file.read_bytes() == content.encode("utf-8")
        finally:
            fw_mod.BASE_DIR = original_base


# ---------------------------------------------------------------------------
# Property 4: file_write path safety
# Feature: engine-real-tools, Property 4: file_write path safety
# ---------------------------------------------------------------------------
@given(
    path=st.one_of(
        # traversal attempts
        st.just("../etc/passwd"),
        st.just("../../secret"),
        st.just("a/../../b"),
        # absolute paths
        st.just("/etc/passwd"),
        st.just("C:\\Windows\\system32\\evil.exe"),
        # generated traversal
        st.builds(
            lambda parts: "/".join(parts),
            st.lists(st.sampled_from([".", "..", "a", "b", "etc"]), min_size=2, max_size=5),
        ),
    )
)
@settings(max_examples=100)
def test_file_write_path_safety(path):
    """Any path with traversal or absolute segments returns an error, never writes outside base."""
    original_base = fw_mod.BASE_DIR
    fw_mod.BASE_DIR = fw_mod.BASE_DIR  # keep real base
    try:
        result = file_write_tool(path, "evil content")
        # If it returned an error string, that's correct
        if "Error" in result or "Write error" in result:
            return
        # If it claimed to write, verify it stayed inside BASE_DIR
        import re
        m = re.search(r"Written \d+ bytes to (.+)", result)
        if m:
            written_path = m.group(1)
            assert str(fw_mod.BASE_DIR) in written_path, (
                f"file_write wrote outside BASE_DIR: {written_path}"
            )
    finally:
        fw_mod.BASE_DIR = original_base


# ---------------------------------------------------------------------------
# Property 5: all tools return str
# Feature: engine-real-tools, Property 5: all tools return str
# ---------------------------------------------------------------------------
@given(
    tool_name=st.sampled_from(["calculator", "file_write"]),
    arg=st.text(max_size=50, alphabet=st.characters(blacklist_characters="\x00")),
)
@settings(max_examples=100)
def test_tools_always_return_str(tool_name, arg):
    """Every tool returns a str for arbitrary string inputs."""
    if tool_name == "calculator":
        result = calculator_tool(arg)
    else:
        result = file_write_tool(arg, arg)
    assert isinstance(result, str), f"{tool_name}('{arg}') returned {type(result)}, not str"
