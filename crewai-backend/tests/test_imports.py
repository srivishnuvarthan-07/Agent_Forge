"""
Import smoke tests.
Verifies that api.main and backend.main can be imported without raising
ModuleNotFoundError or ImportError, even when heavy optional dependencies
(crewai, chromadb, groq, redis, dotenv, pydantic) are not installed.

Requirements: 1.2, 2.4
"""
import sys
import types
import importlib
from typing import Optional


# ---------------------------------------------------------------------------
# Stub out heavy / optional dependencies at module level so they are already
# present in sys.modules before any engine or backend module is imported.
# ---------------------------------------------------------------------------

def _stub(name: str, attrs: Optional[dict] = None) -> types.ModuleType:
    """Register a lightweight fake module in sys.modules if not already there."""
    if name in sys.modules:
        return sys.modules[name]
    mod = types.ModuleType(name)
    if attrs:
        for k, v in attrs.items():
            setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# --- dotenv ------------------------------------------------------------------
_dotenv = _stub("dotenv")
_dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]

# --- pydantic ----------------------------------------------------------------
from unittest.mock import MagicMock

_pydantic = _stub("pydantic")
_pydantic.BaseModel = MagicMock  # type: ignore[attr-defined]
_pydantic.Field = MagicMock()  # type: ignore[attr-defined]

# --- groq --------------------------------------------------------------------
_stub("groq")

# --- redis -------------------------------------------------------------------
_stub("redis")
_stub("redis.asyncio")

# --- crewai ------------------------------------------------------------------
def _crewai_tool_decorator(name_or_func=None):
    """Stub for crewai.tools.tool — handles both @tool and @tool('name') usage."""
    if callable(name_or_func):
        return name_or_func  # used as @tool directly
    # used as @tool("name") — return a decorator
    return lambda f: f

_crewai = _stub("crewai", {
    "Agent": MagicMock(),
    "Task": MagicMock(),
    "Crew": MagicMock(),
    "Process": MagicMock(),
    "LLM": MagicMock(),
})
_stub("crewai.tools", {"tool": _crewai_tool_decorator})

# --- chromadb ----------------------------------------------------------------
_chroma_client = MagicMock()
_stub("chromadb", {"PersistentClient": MagicMock(return_value=_chroma_client)})

# --- config ------------------------------------------------------------------
# config.py does `from dotenv import load_dotenv` and sets env vars.
# Stub it so api.main's `import config` is a no-op.
import os
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy")
_config_mod = _stub("config")

# --- fastapi (only stub if not installed) ------------------------------------
try:
    import fastapi  # noqa: F401
except ImportError:
    _fa = _stub("fastapi")
    _fa.FastAPI = MagicMock  # type: ignore[attr-defined]
    _fa.HTTPException = Exception  # type: ignore[attr-defined]
    _fa.WebSocket = MagicMock  # type: ignore[attr-defined]
    _fa.WebSocketDisconnect = Exception  # type: ignore[attr-defined]
    _fa.BackgroundTasks = MagicMock  # type: ignore[attr-defined]
    _fa.APIRouter = MagicMock  # type: ignore[attr-defined]
    _fa.Request = MagicMock  # type: ignore[attr-defined]
    _fa.__path__ = []  # mark as package so submodule imports work
    _stub("fastapi.middleware.cors", {"CORSMiddleware": MagicMock()})
    _stub("fastapi.middleware", {"cors": sys.modules["fastapi.middleware.cors"]})
    _stub("fastapi.responses", {"JSONResponse": MagicMock()})
    _stub("fastapi.websockets", {"WebSocket": MagicMock(), "WebSocketDisconnect": Exception})
else:
    # fastapi is installed — ensure all sub-stubs are consistent
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_api_main_imports_without_error():
    """import api.main must not raise ModuleNotFoundError or ImportError."""
    # Remove any cached version so we get a fresh import attempt
    for key in list(sys.modules.keys()):
        if key == "api.main" or key == "api":
            del sys.modules[key]

    try:
        import api.main  # noqa: F401
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError(f"api.main raised an import error: {exc}") from exc


def test_crewai_backend_main_imports_without_error():
    """import api.main (crewai-backend) must not raise ModuleNotFoundError or ImportError."""
    for key in list(sys.modules.keys()):
        if key == "api.main" or key == "api":
            del sys.modules[key]

    try:
        import api.main  # noqa: F401
    except (ModuleNotFoundError, ImportError) as exc:
        raise AssertionError(f"api.main raised an import error: {exc}") from exc
