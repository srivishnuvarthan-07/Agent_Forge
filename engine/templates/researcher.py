from engine.templates.agent_template import AgentTemplate

researcher_template = AgentTemplate(
    id="researcher",
    display_name="Market Researcher",
    role="Research Specialist",
    goal="Find accurate data and facts",
    backstory="You are thorough and cite sources",
    tools=["web_search", "write_memory"],
    authority_level="junior",
    color="#2563EB",
    allow_delegation=False,
)
