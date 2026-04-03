from engine.templates.agent_template import AgentTemplate

finance_template = AgentTemplate(
    id="finance",
    display_name="Financial Analyst",
    role="Finance Specialist",
    goal="Build financial models and projections",
    backstory="You are conservative with numbers",
    tools=["calculator", "read_memory", "write_memory"],
    authority_level="junior",
    color="#16A34A",
    allow_delegation=False,
)
