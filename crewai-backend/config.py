"""
Load environment variables before any CrewAI imports.
Must be imported first in any entry point.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Ensure a dummy OpenAI key exists so CrewAI doesn't crash on import.
# We use Groq as the actual LLM provider.
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-dummy-not-used-we-use-groq"
