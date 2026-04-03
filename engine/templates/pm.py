from engine.templates.agent_template import AgentTemplate

pm_template = AgentTemplate(
    id="pm",
    display_name="Product Manager",
    role="Product Specialist",
    goal="Define requirements and prioritize features",
    backstory="You balance user needs with business goals",
    tools=["spawn_agent", "read_memory", "write_memory"],
    authority_level="manager",
    color="#9333EA",
    allow_delegation=True,
)
