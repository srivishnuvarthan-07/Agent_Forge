"""
Safe file write tool — restricts all writes to workspace/output/.
"""
from __future__ import annotations
import re
from pathlib import Path
from crewai.tools import tool

BASE_DIR = Path("workspace/output").resolve()

_WINDOWS_ABS = re.compile(r"^[A-Za-z]:[/\\]")


@tool("file_write")
def file_write_tool(path: str, content: str) -> str:
    """Write content to a file inside workspace/output/. Args: path, content."""
    if not path or not path.strip():
        return "Error: path must be a non-empty string"

    # Reject absolute paths
    p = Path(path)
    if p.is_absolute() or _WINDOWS_ABS.match(path):
        return "Error: absolute paths are not allowed"

    # Reject traversal segments
    if ".." in p.parts:
        return "Error: path traversal is not allowed"

    try:
        resolved = (BASE_DIR / path).resolve()
        # Symlink-safe double-check
        if not str(resolved).startswith(str(BASE_DIR)):
            return "Error: path traversal is not allowed"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        byte_content = content.encode("utf-8")
        resolved.write_bytes(byte_content)
        return f"Written {len(byte_content)} bytes to {resolved}"
    except OSError as e:
        return f"Write error: {e}"
    except Exception as e:
        return f"Write error: {e}"
