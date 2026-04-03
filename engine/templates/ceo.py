from engine.templates.agent_template import AgentTemplate

ceo_template = AgentTemplate(
    id="ceo",
    display_name="CEO Agent",
    role="Chief Executive Officer",
    goal="Delegate tasks and synthesize final output",
    backstory="You are a decisive leader who hires specialists",
    tools=["spawn_agent", "delegate_task"],
    authority_level="executive",
    color="#DC2626",
    allow_delegation=True,
)
