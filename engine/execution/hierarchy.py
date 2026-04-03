import config  # Load env vars before CrewAI imports
from uuid import uuid4
import os
import logging
import threading
from dataclasses import dataclass, field
from crewai import Agent, Task, Crew, Process, LLM
from engine.templates.registry import get_template, _MEMORY_TOOL_MAP
from engine.memory.crew_memory import CrewMemoryManager
from engine.websocket.emitter import EventEmitter, emitter as _default_emitter

DELEGATION_LEVELS = {"executive", "manager"}
MAX_SPAWN_DEPTH = 3  # prevent infinite recursion


@dataclass
class SpawnRequest:
    template_id: str
    task_description: str
    parent_id: str
    depth: int = 0


# Module-level registry: maps crew_id → HierarchyEngine instance
# Allows spawn_agent tool to push requests into the running engine
_active_engines: dict[str, "HierarchyEngine"] = {}
_engines_lock = threading.Lock()


def get_active_engine(crew_id: str) -> "HierarchyEngine | None":
    with _engines_lock:
        return _active_engines.get(crew_id)


def _register_engine(crew_id: str, engine: "HierarchyEngine") -> None:
    with _engines_lock:
        _active_engines[crew_id] = engine


def _unregister_engine(crew_id: str) -> None:
    with _engines_lock:
        _active_engines.pop(crew_id, None)


def _get_llm():
    """Return a Groq LLM if GROQ_API_KEY is set, otherwise let CrewAI use its default."""
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return LLM(model="groq/llama-3.3-70b-versatile", api_key=groq_key)
    return None


class HierarchyEngine:

    def __init__(self, event_emitter: EventEmitter = None):
        self.crew_memory: CrewMemoryManager | None = None
        self.emitter: EventEmitter = event_emitter or _default_emitter
        self._spawn_queue: list[SpawnRequest] = []
        self._spawn_lock = threading.Lock()
        self._current_crew_id: str | None = None

    def enqueue_spawn(self, template_id: str, task_description: str,
                      parent_id: str, depth: int = 0) -> bool:
        """Thread-safe: push a spawn request from the spawn_agent tool. Returns False if depth exceeded."""
        if depth >= MAX_SPAWN_DEPTH:
            logging.warning("spawn_agent: max depth %d reached, ignoring spawn of '%s'",
                            MAX_SPAWN_DEPTH, template_id)
            return False
        with self._spawn_lock:
            self._spawn_queue.append(SpawnRequest(template_id, task_description, parent_id, depth))
        return True

    def parse_canvas(self, nodes: list[dict], edges: list[dict]) -> dict:
        node_map: dict[str, dict] = {n["id"]: n for n in nodes}
        has_parent: set[str] = set()
        children: dict[str, list[dict]] = {n["id"]: [] for n in nodes}
        collaborations: list[tuple[dict, dict]] = []

        for edge in edges:
            source_id = edge["source"]
            target_id = edge["target"]
            if edge.get("type") == "collaborates_with":
                if source_id in node_map and target_id in node_map:
                    collaborations.append((node_map[source_id], node_map[target_id]))
                continue
            has_parent.add(target_id)
            if source_id in children and target_id in node_map:
                children[source_id].append(node_map[target_id])

        roots = [
            n for n in nodes
            if n["id"] not in has_parent
            and n.get("authority_level") == "executive"
        ]

        return {
            "roots": roots,
            "children": children,
            "collaborations": collaborations,
            "node_map": node_map,
        }

    def instantiate_agent(self, node: dict) -> Agent:
        template = get_template(node["id"])
        allow_delegation = template.authority_level in DELEGATION_LEVELS
        agent_id = node["id"]
        emitter = self.emitter

        def step_callback(step):
            emitter.agent_thinking(agent_id, str(getattr(step, "output", step))[:300])

        resolved_tools = [_MEMORY_TOOL_MAP[t] for t in template.tools if t in _MEMORY_TOOL_MAP]
        for tool in resolved_tools:
            tool_name = getattr(tool, "name", "") or ""
            tool_desc = getattr(tool, "description", "") or ""
            if "[stub]" in tool_name or "[stub]" in tool_desc:
                logging.warning("Agent '%s' is using stub tool: %s", agent_id, tool_name)

        agent = Agent(
            role=template.role,
            goal=template.goal,
            backstory=template.backstory,
            tools=resolved_tools,
            allow_delegation=allow_delegation,
            verbose=True,
            step_callback=step_callback,
            llm=_get_llm(),
        )
        # Store metadata for task_callback lookup in build_crew
        agent._aw_agent_id = agent_id
        agent._aw_role = template.role
        return agent

    def build_crew(self, root_node: dict, children_map: dict[str, list[dict]]) -> Crew:
        manager_agent = self.instantiate_agent(root_node)
        child_agents: list[Agent] = []
        all_tasks: list[Task] = []
        child_output_refs: list[str] = []

        # Create child agents (these go in agents list)
        for child in children_map.get(root_node["id"], []):
            child_agent = self.instantiate_agent(child)
            child_agents.append(child_agent)
            
            # Create task for each child
            child_task = Task(
                description=f"As {child['id']}, complete your specialized task and provide output.",
                expected_output=f"Detailed output from {child['id']} agent.",
                agent=child_agent,
            )
            all_tasks.append(child_task)
            child_output_refs.append(f"[output:{child['id']}]")

        # Manager task that synthesizes child outputs
        child_summary = ", ".join(child_output_refs) if child_output_refs else "no sub-tasks"
        description = (
            f"As {root_node['id']}, synthesize the following child outputs: {child_summary}. "
            f"Produce a final consolidated result."
        )
        if self.crew_memory:
            task_keywords = root_node.get("task_description", "").split()[:5]
            context = self.crew_memory.get_context_for_agent(root_node["id"], task_keywords)
            if context:
                description = f"{context}\n\n{description}"

        manager_task = Task(
            description=description,
            expected_output="A comprehensive summary incorporating all child agent outputs.",
            agent=manager_agent,
        )
        all_tasks.append(manager_task)

        return Crew(
            agents=child_agents,  # Only child agents, not manager
            tasks=all_tasks,
            process=Process.hierarchical,
            manager_agent=manager_agent,
            verbose=True,
        )

    def execute(self, nodes: list[dict], edges: list[dict], crew_id: str = None) -> str:
        """Parse canvas, enforce single executive root, inject memory, run crew."""
        parsed = self.parse_canvas(nodes, edges)
        roots = parsed["roots"]

        if not roots:
            raise ValueError("No executive root node found. Add a CEO/executive agent.")
        if len(roots) > 1:
            raise ValueError(
                f"Expected exactly one executive root, found {len(roots)}: "
                + ", ".join(r["id"] for r in roots)
            )

        crew_id = crew_id or f"crew_{uuid4().hex[:8]}"
        self._current_crew_id = crew_id
        self.crew_memory = CrewMemoryManager(crew_id)
        root = roots[0]
        crew = self.build_crew(root, parsed["children"])

        _register_engine(crew_id, self)
        # Tell spawn_agent tool which crew is active
        try:
            from engine.tools.spawn_agent import set_current_crew_id
            set_current_crew_id(crew_id)
        except Exception:
            pass
        try:
            result = crew.kickoff()
            result_str = str(result)

            # ── Drain spawn queue ─────────────────────────────────────────────
            spawn_results = self._drain_spawn_queue()
            if spawn_results:
                combined = result_str + "\n\n--- Spawned Agent Results ---\n" + "\n".join(spawn_results)
                self.emitter.crew_finished(crew_id, combined[:500])
                return combined
            else:
                self.emitter.crew_finished(crew_id, result_str[:500])
                return result_str

        except Exception as e:
            self.emitter.agent_error("crew", str(e))
            raise
        finally:
            _unregister_engine(crew_id)
            self._current_crew_id = None
            try:
                from engine.tools.spawn_agent import set_current_crew_id
                set_current_crew_id(None)
            except Exception:
                pass

    def _drain_spawn_queue(self) -> list[str]:
        """Run all queued spawn requests sequentially. Returns list of result strings."""
        results = []
        while True:
            with self._spawn_lock:
                if not self._spawn_queue:
                    break
                req = self._spawn_queue.pop(0)

            try:
                template = get_template(req.template_id)
            except KeyError:
                logging.warning("_drain_spawn_queue: unknown template '%s'", req.template_id)
                continue

            node = {"id": f"{req.template_id}_{uuid4().hex[:8]}"}
            agent = self.instantiate_agent(node)
            task = Task(
                description=req.task_description,
                expected_output=f"Output from dynamically spawned {req.template_id} agent.",
                agent=agent,
            )
            mini_crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=True,
            )
            try:
                self.emitter.agent_started(node["id"], template.role)
                output = mini_crew.kickoff()
                output_str = str(output)
                self.emitter.agent_completed(node["id"], output_str[:300])
                results.append(f"[{req.template_id}] {output_str}")
            except Exception as e:
                self.emitter.agent_error(node["id"], str(e))
                results.append(f"[{req.template_id}] Error: {e}")

        return results
