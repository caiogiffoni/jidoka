"""Shared test helpers for driving the agent graph with a deterministic LLM.

These fakes live outside individual test files so unit, integration, and
acceptance tests can all exercise the same HITL flow without calling OpenAI.
"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeToolCallingModel(BaseChatModel):
    """A deterministic LLM that always requests the create_task tool with the
    supplied arguments.
    """

    tool_args: dict[str, Any]

    @property
    def _llm_type(self) -> str:
        return "fake_tool_calling_model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Standard LangChain tool-call shape so AIMessage validates it directly.
        tool_call = {
            "id": "call_1",
            "name": "create_task",
            "args": self.tool_args,
        }
        message = AIMessage(content="", tool_calls=[tool_call])
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation], llm_output={})

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"tool_args": self.tool_args}
