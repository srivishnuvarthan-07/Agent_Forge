from __future__ import annotations

import json
from datetime import datetime, timezone

try:
    from engine.websocket.emitter import emitter as _emitter
except Exception:
    _emitter = None

try:
    import chromadb
    _client = chromadb.PersistentClient(path="./chroma_db")
    _USE_CHROMA = True
except ImportError:
    _client = None
    _USE_CHROMA = False

COLLECTIONS = ["facts", "work_in_progress", "decisions", "conflicts"]


def _get_collection(name: str):
    if _USE_CHROMA:
        return _client.get_or_create_collection(name)
    return None


# Fallback in-memory store: { collection: { key: entry } }
_fallback: dict[str, dict] = {c: {} for c in COLLECTIONS}


class SharedMemory:

    def write(
        self,
        key: str,
        value: str,
        source_agent: str,
        collection: str = "work_in_progress",
        confidence: float = 0.8,
        metadata: dict = {},
        manager_approved: bool = False,
    ) -> dict:
        """
        Write a value to the specified collection.

        Rules:
          - "facts" collection requires confidence > 0.9 OR manager_approved=True
          - All entries are stored with timestamp, source_agent, and version metadata
        """
        if collection not in COLLECTIONS:
            raise ValueError(f"Unknown collection '{collection}'. Choose from {COLLECTIONS}.")

        if collection == "facts" and confidence <= 0.9 and not manager_approved:
            raise PermissionError(
                f"Cannot write to 'facts': confidence {confidence} <= 0.9 and no manager approval."
            )

        timestamp = datetime.now(timezone.utc).isoformat()

        entry_metadata = {
            "source_agent": source_agent,
            "timestamp": timestamp,
            "confidence": confidence,
            "manager_approved": manager_approved,
            **metadata,
        }

        if _USE_CHROMA:
            col = _get_collection(collection)
            # Chroma upsert — version tracked via timestamp in metadata
            existing = col.get(ids=[key])
            existing_entry = None
            if existing["ids"]:
                existing_entry = {
                    "value": existing["documents"][0],
                    "metadata": existing["metadatas"][0],
                }
            if existing_entry:
                from engine.memory.conflict_detector import ConflictDetector, create_conflict
                detector = ConflictDetector()
                result = detector.detect_conflict(key, value, existing_entry)
                if result["conflict"]:
                    create_conflict(
                        key,
                        existing_entry["value"],
                        existing_entry["metadata"].get("source_agent", "unknown"),
                        value,
                        source_agent,
                    )
            version = len(existing["ids"]) + 1 if existing["ids"] else 1
            entry_metadata["version"] = version
            col.upsert(
                ids=[key],
                documents=[value],
                metadatas=[entry_metadata],
            )
        else:
            existing_entry = _fallback[collection].get(key)
            if existing_entry:
                from engine.memory.conflict_detector import ConflictDetector, create_conflict
                detector = ConflictDetector()
                result = detector.detect_conflict(key, value, existing_entry)
                if result["conflict"]:
                    create_conflict(
                        key,
                        existing_entry["value"],
                        existing_entry["metadata"].get("source_agent", "unknown"),
                        value,
                        source_agent,
                    )
            version = (existing_entry["metadata"].get("version", 0) + 1) if existing_entry else 1
            entry_metadata["version"] = version
            _fallback[collection][key] = {"value": value, "metadata": entry_metadata}

        if _emitter:
            _emitter.memory_update(key, collection, source_agent)
        return {"key": key, "collection": collection, "version": version, "timestamp": timestamp}

    def read(self, key: str, collection: str = None) -> dict | None:
        """Retrieve an entry by exact key. Searches all collections if collection=None."""
        search = [collection] if collection else COLLECTIONS
        for col_name in search:
            if _USE_CHROMA:
                result = _get_collection(col_name).get(ids=[key])
                if result["ids"]:
                    return {
                        "key": key,
                        "value": result["documents"][0],
                        "metadata": result["metadatas"][0],
                        "collection": col_name,
                    }
            else:
                entry = _fallback[col_name].get(key)
                if entry:
                    return {"key": key, **entry, "collection": col_name}
        return None

    def query(self, query_text: str, n_results: int = 5, collection: str = None) -> list[dict]:
        """Semantic search via ChromaDB embeddings, or substring match fallback."""
        search = [collection] if collection else COLLECTIONS
        results = []
        for col_name in search:
            if _USE_CHROMA:
                col = _get_collection(col_name)
                res = col.query(query_texts=[query_text], n_results=n_results)
                for i, doc_id in enumerate(res["ids"][0]):
                    results.append({
                        "key": doc_id,
                        "value": res["documents"][0][i],
                        "metadata": res["metadatas"][0][i],
                        "collection": col_name,
                        "distance": res["distances"][0][i],
                    })
            else:
                q = query_text.lower()
                for key, entry in _fallback[col_name].items():
                    if q in entry["value"].lower() or q in key.lower():
                        results.append({"key": key, **entry, "collection": col_name})
        return results[:n_results]

    def get_by_agent(self, agent_id: str, collection: str = None) -> list[dict]:
        """Return all entries written by a specific agent."""
        search = [collection] if collection else COLLECTIONS
        results = []
        for col_name in search:
            if _USE_CHROMA:
                res = _get_collection(col_name).get(where={"source_agent": agent_id})
                for i, doc_id in enumerate(res["ids"]):
                    results.append({
                        "key": doc_id,
                        "value": res["documents"][i],
                        "metadata": res["metadatas"][i],
                        "collection": col_name,
                    })
            else:
                for key, entry in _fallback[col_name].items():
                    if entry["metadata"].get("source_agent") == agent_id:
                        results.append({"key": key, **entry, "collection": col_name})
        return results

    def update(self, key: str, new_value: str, source_agent: str, reason: str) -> dict:
        """Update an existing entry, preserving version history via metadata."""
        existing = self.read(key)
        if not existing:
            raise KeyError(f"Key '{key}' not found in any collection.")
        col = existing["collection"]
        prev_version = existing["metadata"].get("version", 1)
        return self.write(
            key=key,
            value=new_value,
            source_agent=source_agent,
            collection=col,
            confidence=existing["metadata"].get("confidence", 0.8),
            metadata={"reason": reason, "previous_version": prev_version},
            manager_approved=existing["metadata"].get("manager_approved", False),
        )

    def promote_to_fact(self, key: str, approving_agent: str = "system") -> dict:
        """Move an entry from work_in_progress to facts collection."""
        entry = self.read(key, collection="work_in_progress")
        if not entry:
            raise KeyError(f"Key '{key}' not found in work_in_progress.")
        result = self.write(
            key=key,
            value=entry["value"],
            source_agent=entry["metadata"]["source_agent"],
            collection="facts",
            confidence=1.0,
            metadata={"promoted_by": approving_agent},
            manager_approved=True,
        )
        # Remove from work_in_progress
        if _USE_CHROMA:
            _get_collection("work_in_progress").delete(ids=[key])
        else:
            _fallback["work_in_progress"].pop(key, None)
        return result
