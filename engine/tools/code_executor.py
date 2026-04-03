"""
Sandboxed Python code executor.
Pre-scans AST for restricted imports, then runs code in a subprocess with timeout.
"""
from __future__ import annotations
import ast
import subprocess
import sys
from crewai.tools import tool

RESTRICTED_MODULES = {"os", "sys", "subprocess", "shutil", "socket", "pathlib"}
TIMEOUT_SECONDS = 10


def _check_restricted_imports(code: str) -> str | None:
    """Return an error string if restricted imports are found, else None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in RESTRICTED_MODULES:
                    return f"Error: import of restricted module '{root}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in RESTRICTED_MODULES:
                    return f"Error: import of restricted module '{root}' is not allowed"
    return None


@tool("code_executor")
def code_executor_tool(code: str) -> str:
    """Execute Python code in a sandboxed subprocess. Args: code."""
    if not code or not code.strip():
        return "Error: no code provided"

    error = _check_restricted_imports(code)
    if error:
        return error

    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return f"Error: {stderr}" if stderr else "Error: non-zero exit code"
        stdout = result.stdout.strip()
        return stdout if stdout else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: execution timed out after {TIMEOUT_SECONDS} seconds"
    except Exception as e:
        return f"Error: {e}"
