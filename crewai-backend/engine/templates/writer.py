from engine.templates.agent_template import AgentTemplate

writer_template = AgentTemplate(
    id="writer",
    display_name="Content Writer",
    role="Writing Specialist",
    goal="Create clear, compelling content",
    backstory="You adapt tone for the audience",
    tools=["read_memory", "write_memory"],
    authority_level="junior",
    color="#7C3AED",
    allow_delegation=False,
)
