from engine.templates.agent_template import AgentTemplate
from engine.templates.ceo import ceo_template
from engine.templates.researcher import researcher_template
from engine.templates.analyst import analyst_template
from engine.templates.writer import writer_template
from engine.templates.critic import critic_template
from engine.templates.developer import developer_template
from engine.templates.designer import designer_template
from engine.templates.pm import pm_template
from engine.templates.marketing import marketing_template
from engine.templates.finance import finance_template

# Memory tools
from engine.memory.tools import memory_write_tool, memory_read_tool, memory_query_tool

# Real tool implementations
from engine.tools.web_search import web_search_tool
from engine.tools.code_executor import code_executor_tool
from engine.tools.file_write import file_write_tool
from engine.tools.spawn_agent import spawn_agent_tool
from engine.tools.delegate_task import delegate_task_tool
from engine.tools.calculator import calculator_tool
from engine.tools.flag_conflict import flag_conflict_tool

# Single lookup table used by HierarchyEngine.instantiate_agent
_MEMORY_TOOL_MAP = {
    "write_memory":  memory_write_tool,
    "read_memory":   memory_read_tool,
    "query_memory":  memory_query_tool,
    "web_search":    web_search_tool,
    "code_executor": code_executor_tool,
    "file_write":    file_write_tool,
    "spawn_agent":   spawn_agent_tool,
    "delegate_task": delegate_task_tool,
    "calculator":    calculator_tool,
    "flag_conflict": flag_conflict_tool,
}

_registry: dict[str, AgentTemplate] = {
    t.id: t for t in [
        ceo_template,
        researcher_template,
        analyst_template,
        writer_template,
        critic_template,
        developer_template,
        designer_template,
        pm_template,
        marketing_template,
        finance_template,
    ]
}


def get_template(template_id: str) -> AgentTemplate:
    """Return a template by id."""
    if template_id not in _registry:
        raise KeyError(f"Template '{template_id}' not found.")
    return _registry[template_id]


def list_templates() -> list[AgentTemplate]:
    """Return all registered templates."""
    return list(_registry.values())
