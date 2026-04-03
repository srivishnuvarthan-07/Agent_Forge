"""
CrewAI Backend — entry point.
Run with: uvicorn main:app --reload --port 8000
Or:        python main.py
"""
import sys
from pathlib import Path

# Ensure crewai-backend/ is on the path so `import config`, `import api`, etc. resolve
sys.path.insert(0, str(Path(__file__).parent))

import config  # noqa: E402 — must load env before crewai
from api.main import app  # noqa: E402

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
