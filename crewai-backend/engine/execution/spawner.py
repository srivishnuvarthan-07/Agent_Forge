import asyncio
import random
from uuid import uuid4
from crewai import Agent
from engine.templates.registry import get_template
from engine.websocket.manager import manager
from engine.websocket.emitter import emitter

DELEGATION_LEVELS = {"executive", "manager"}


class AgentSpawner:

    def spawn_agent(
        self,
        template_id: str,
        parent_id: str,
        task_description: str,
        current_nodes: list[dict],
    ) -> str:
        """
        Dynamically create a new agent node mid-execution.
        Broadcasts a WebSocket event, adds to execution queue.
        Returns the new agent's unique ID.
        """
        unique_id = f"{template_id}_{uuid4().hex[:8]}"

        parent_node = next((n for n in current_nodes if n["id"] == parent_id), None)
        parent_x = parent_node["position"]["x"] if parent_node else 0
        parent_y = parent_node["position"]["y"] if parent_node else 0

        offset_x = random.randint(150, 300) * random.choice([-1, 1])
        offset_y = random.randint(100, 200)

        template = get_template(template_id)
        allow_delegation = template.authority_level in DELEGATION_LEVELS

        node = {
            "id": unique_id,
            "template_id": template_id,
            "display_name": template.display_name,
            "authority_level": template.authority_level,
            "color": template.color,
            "task_description": task_description,
            "parent_id": parent_id,
            "position": {
                "x": parent_x + offset_x,
                "y": parent_y + offset_y,
            },
        }

        agent = Agent(
            role=template.role,
            goal=template.goal,
            backstory=template.backstory,
            tools=[],
            allow_delegation=allow_delegation,
            verbose=True,
        )

        event = {"type": "agent_spawned", "parent_id": parent_id, "new_agent": node}

        # Broadcast to WebSocket clients (fire-and-forget)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(manager.broadcast(event))
            else:
                loop.run_until_complete(manager.broadcast(event))
        except RuntimeError:
            pass

        # Emit structured event
        emitter.agent_spawned(parent_id, node)

        return unique_id
