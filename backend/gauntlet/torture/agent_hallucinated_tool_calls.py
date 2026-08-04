"""Simulate an LLM returning hallucinated tool calls and assert no DB writes."""

import os
import sys
import uuid
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.errors import GraphInterrupt
from sqlmodel import Session, select

os.environ.setdefault(
    "JWT_SECRET_KEY", "torture-secret-must-be-at-least-32-bytes-long"
)

import auth
import db
from agent.graph import build_graph
from models import Project, Task, User


class BadToolCallModel(BaseChatModel):
    """Deterministic LLM that always emits the supplied bad tool call."""

    tool_name: str
    tool_args: dict[str, Any]

    @property
    def _llm_type(self) -> str:
        return "bad_tool_call_model"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        tool_call = {
            "id": "call_1",
            "type": "tool_call",
            "function": {"name": self.tool_name, "arguments": self.tool_args},
        }
        message = AIMessage(content="", tool_calls=[tool_call])
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation], llm_output={})

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"tool_name": self.tool_name, "tool_args": self.tool_args}


def make_user(session: Session, suffix: str) -> User:
    user = User(
        email=f"{suffix}@example.com",
        username=suffix,
        hashed_password=auth._hash_password("Password1!"),
    )
    session.add(user)
    session.flush()
    return user


def task_count(session: Session) -> int:
    return len(session.exec(select(Task)).all())


def run_case(session: Session, user: User, label: str, model: BaseChatModel) -> bool:
    graph = build_graph(model=model)
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id, "user": user}}
    before = task_count(session)
    raised = None

    try:
        graph.invoke(
            {"messages": [{"role": "user", "content": "do something"}]},
            config=config,
        )
    except GraphInterrupt:
        try:
            from langgraph.types import Command

            graph.invoke(Command(resume={"approved": True}), config=config)
        except Exception as exc:
            raised = exc
    except Exception as exc:
        raised = exc

    after = task_count(session)
    if after != before:
        print(f"FAIL {label}: task count changed {before} -> {after}")
        return False

    if raised is None:
        print(f"FAIL {label}: expected an error but graph completed cleanly")
        return False

    print(f"OK   {label}: {type(raised).__name__}")
    return True


def main() -> int:
    db.create_db_and_tables()
    connection = db.engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    try:
        user1 = make_user(session, "hallucinated1")
        user2 = make_user(session, "hallucinated2")
        project2 = Project(name="Other project", user_id=user2.id)
        session.add(project2)
        session.flush()

        cases = [
            (
                "non-existent tool",
                BadToolCallModel(tool_name="delete_everything", tool_args={}),
            ),
            (
                "blank title",
                BadToolCallModel(tool_name="create_task", tool_args={"title": "   "}),
            ),
            (
                "invalid column_id",
                BadToolCallModel(
                    tool_name="create_task",
                    tool_args={"title": "Bad column", "column_id": "blocked"},
                ),
            ),
            (
                "project_id not owned by user",
                BadToolCallModel(
                    tool_name="create_task",
                    tool_args={
                        "title": "Stolen project",
                        "column_id": "todo",
                        "project_id": str(project2.id),
                    },
                ),
            ),
        ]

        passed = 0
        for label, model in cases:
            if run_case(session, user1, label, model):
                passed += 1

        print(f"\n{passed}/{len(cases)} passed")
        return 0 if passed == len(cases) else 1
    finally:
        session.close()
        transaction.rollback()
        connection.close()


if __name__ == "__main__":
    sys.exit(main())
