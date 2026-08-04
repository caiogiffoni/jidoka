"""LangGraph state machine for the HITL board agent."""

from langchain_core.language_models.chat_models import BaseChatModel


def build_graph(model: BaseChatModel | None = None):
    """Compile and return the HITL agent graph."""
    raise NotImplementedError("agent graph not yet implemented")


# Default model loaded from environment for the production router.
model = None
