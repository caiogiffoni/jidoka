"""LLM-test fixtures.

Loads the root `.env` file so `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are
available without manually exporting them before each run.
"""

from pathlib import Path

from dotenv import load_dotenv

# tests/llm/conftest.py -> tests/llm -> tests -> backend -> project root
_ROOT_DOTENV = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(_ROOT_DOTENV, override=False)
