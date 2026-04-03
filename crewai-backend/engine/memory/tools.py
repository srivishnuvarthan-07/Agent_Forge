from crewai.tools import tool
from engine.memory.store import SharedMemory

_memory = SharedMemory()


@tool("memory_write_tool")
def memory_write_tool(key: str, value: str, confidence: float = 0.8) -> str:
    """Write a key-value pair to shared memory. Args: key, value, confidence (0.0-1.0)."""
    try:
        result = _memory.write(
            key=key,
            value=value,
            source_agent="agent",
            confidence=confidence,
        )
        return f"Stored '{key}' in {result['collection']} (version {result['version']})."
    except PermissionError as e:
        return f"Write blocked: {e}"
    except Exception as e:
        return f"Write failed: {e}"


@tool("memory_read_tool")
def memory_read_tool(key: str) -> str:
    """Read a value from shared memory by exact key. Args: key."""
    entry = _memory.read(key)
    if not entry:
        return "Not found"
    meta = entry.get("metadata", {})
    return (
        f"[{entry['collection']}] {entry['value']} "
        f"(source: {meta.get('source_agent', '?')}, v{meta.get('version', 1)})"
    )


@tool("memory_query_tool")
def memory_query_tool(query: str) -> str:
    """Search shared memory semantically. Returns top 5 relevant entries. Args: query."""
    results = _memory.query(query, n_results=5)
    if not results:
        return "No relevant memories found."
    lines = []
    for r in results:
        lines.append(f"- [{r['collection']}] {r['key']}: {r['value'][:120]}")
    return "\n".join(lines)
