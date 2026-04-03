from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentTemplate:
    id: str
    display_name: str
    role: str
    goal: str
    backstory: str
    tools: List[str] = field(default_factory=list)
    authority_level: str = "standard"
    color: str = "#ffffff"
    max_iterations: int = 10
    allow_delegation: bool = False
