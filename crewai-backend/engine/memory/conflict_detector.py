import re

# Keywords that signal explicit disagreement
DISAGREEMENT_KEYWORDS = [
    "disagree", "incorrect", "wrong", "false", "not true",
    "contradicts", "dispute", "inaccurate", "misleading", "invalid",
]


def _similarity(a: str, b: str) -> float:
    """Simple Jaccard similarity on word sets."""
    a_words = set(re.findall(r"\w+", a.lower()))
    b_words = set(re.findall(r"\w+", b.lower()))
    if not a_words and not b_words:
        return 1.0
    intersection = a_words & b_words
    union = a_words | b_words
    return len(intersection) / len(union)


class ConflictDetector:

    def detect_conflict(
        self,
        key: str,
        new_value: str,
        existing_entry: dict,
    ) -> dict:
        """
        Compare new_value against existing_entry to detect conflicts.

        Returns:
            {
                "conflict": bool,
                "reason": str,
                "similarity": float,
                "severity": "low" | "medium" | "high"
            }
        """
        existing_value = existing_entry.get("value", "")
        similarity = _similarity(new_value, existing_value)

        # Check for explicit disagreement keywords in new value
        new_lower = new_value.lower()
        has_disagreement_keyword = any(kw in new_lower for kw in DISAGREEMENT_KEYWORDS)

        conflict = False
        reason = "No conflict detected."
        severity = "low"

        if has_disagreement_keyword:
            conflict = True
            reason = "New value contains explicit disagreement language."
            severity = "high"
        elif similarity < 0.2:
            conflict = True
            reason = f"Values are highly dissimilar (similarity={similarity:.2f})."
            severity = "medium"
        elif similarity < 0.4:
            conflict = True
            reason = f"Values diverge significantly (similarity={similarity:.2f})."
            severity = "low"

        return {
            "conflict": conflict,
            "key": key,
            "reason": reason,
            "similarity": round(similarity, 4),
            "severity": severity,
            "existing_source": existing_entry.get("metadata", {}).get("source_agent", "unknown"),
        }


# Module-level SharedMemory instance for conflict persistence
from engine.memory.store import SharedMemory as _SharedMemory
from engine.websocket.emitter import emitter as _emitter
_store = _SharedMemory()


def create_conflict(
    key: str,
    value_a: str,
    agent_a: str,
    value_b: str,
    agent_b: str,
) -> dict:
    """Write a conflict record to the conflicts collection."""
    import json
    conflict_value = json.dumps({
        "value_a": value_a,
        "agent_a": agent_a,
        "value_b": value_b,
        "agent_b": agent_b,
        "resolved": False,
    })
    result = _store.write(
        key=f"conflict_{key}",
        value=conflict_value,
        source_agent="system",
        collection="conflicts",
        confidence=1.0,
        metadata={"original_key": key, "resolved": False},
        manager_approved=True,
    )
    _emitter.conflict_detected(key, agent_a, agent_b, "medium")
    return result


def get_conflicts_for_resolution(manager_id: str) -> list[dict]:
    """Return all unresolved conflicts for a manager to review."""
    all_conflicts = _store.get_by_agent("system", collection="conflicts")
    return [
        c for c in all_conflicts
        if not c.get("metadata", {}).get("resolved", False)
    ]


def resolve_conflict(key: str, resolution: str, resolved_by: str) -> dict:
    """Move a conflict to the decisions collection as resolved."""
    import json
    conflict_key = f"conflict_{key}" if not key.startswith("conflict_") else key
    entry = _store.read(conflict_key, collection="conflicts")
    if not entry:
        raise KeyError(f"Conflict '{conflict_key}' not found.")

    # Write resolution to decisions
    result = _store.write(
        key=f"decision_{key}",
        value=resolution,
        source_agent=resolved_by,
        collection="decisions",
        confidence=1.0,
        metadata={"original_conflict_key": conflict_key, "resolved_by": resolved_by},
        manager_approved=True,
    )

    # Mark conflict as resolved
    import json as _json
    try:
        conflict_data = _json.loads(entry["value"])
    except Exception:
        conflict_data = {}
    conflict_data["resolved"] = True
    _store.write(
        key=conflict_key,
        value=_json.dumps(conflict_data),
        source_agent=resolved_by,
        collection="conflicts",
        confidence=1.0,
        metadata={"resolved": True, "resolved_by": resolved_by},
        manager_approved=True,
    )
    _emitter.conflict_resolved(key, resolved_by, resolution)
    return result
