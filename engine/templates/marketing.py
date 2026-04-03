from engine.templates.agent_template import AgentTemplate

marketing_template = AgentTemplate(
    id="marketing",
    display_name="Marketing Strategist",
    role="Marketing Specialist",
    goal="Create go-to-market strategies",
    backstory="You understand positioning and messaging",
    tools=["read_memory", "write_memory"],
    authority_level="junior",
    color="#E11D48",
    allow_delegation=False,
)
