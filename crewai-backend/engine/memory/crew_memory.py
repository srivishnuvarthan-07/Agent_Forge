from __future__ import annotations

from engine.memory.store import SharedMemory


class CrewMemoryManager:
    """Wraps SharedMemory scoped to a specific crew instance."""

    def __init__(self, crew_id: str):
        self.crew_id = crew_id
        self._store = SharedMemory()

    def _scoped_key(self, key: str) -> str:
        return f"{self.crew_id}:{key}"

    def write(self, key: str, value: str, source_agent: str, **kwargs) -> dict:
        return self._store.write(
            key=self._scoped_key(key),
            value=value,
            source_agent=source_agent,
            metadata={"crew_id": self.crew_id},
            **kwargs,
        )

    def read(self, key: str, collection: str = None) -> dict | None:
        return self._store.read(self._scoped_key(key), collection=collection)

    def query(self, query_text: str, n_results: int = 5, collection: str = None) -> list[dict]:
        results = self._store.query(query_text, n_results=n_results * 2, collection=collection)
        # Filter to this crew's entries where possible
        crew_results = [r for r in results if r.get("metadata", {}).get("crew_id") == self.crew_id]
        return (crew_results or results)[:n_results]

    def get_all(self, collection: str = None) -> list[dict]:
        """Return all memory entries belonging to this crew."""
        from engine.memory.store import COLLECTIONS, _USE_CHROMA, _fallback, _get_collection
        search = [collection] if collection else COLLECTIONS
        results = []
        for col_name in search:
            if _USE_CHROMA:
                res = _get_collection(col_name).get(where={"crew_id": self.crew_id})
                for i, doc_id in enumerate(res["ids"]):
                    results.append({
                        "key": doc_id,
                        "value": res["documents"][i],
                        "metadata": res["metadatas"][i],
                        "collection": col_name,
                    })
            else:
                for key, entry in _fallback[col_name].items():
                    if entry["metadata"].get("crew_id") == self.crew_id:
                        results.append({"key": key, **entry, "collection": col_name})
        return results

    def promote_to_fact(self, key: str, approving_agent: str = "system") -> dict:
        return self._store.promote_to_fact(self._scoped_key(key), approving_agent)

    def update(self, key: str, new_value: str, source_agent: str, reason: str) -> dict:
        return self._store.update(self._scoped_key(key), new_value, source_agent, reason)

    def get_context_for_agent(self, agent_id: str, task_keywords: list[str] = None) -> str:
        """
        Return a formatted context string of relevant memories for an agent.
        Queries by agent's own past writes + task keywords.
        """
        summaries = []

        # 1. Retrieve this agent's own prior contributions
        own_entries = self._store.get_by_agent(agent_id)
        for e in own_entries[:3]:
            summaries.append(f"{e['key'].split(':')[-1]}: {e['value'][:100]}")

        # 2. Query by task keywords across all collections
        if task_keywords:
            for kw in task_keywords[:3]:
                results = self.query(kw, n_results=2)
                for r in results:
                    entry_summary = f"{r['key'].split(':')[-1]}: {r['value'][:100]}"
                    if entry_summary not in summaries:
                        summaries.append(entry_summary)

        if not summaries:
            return ""

        return "Previous findings: " + " | ".join(summaries)
