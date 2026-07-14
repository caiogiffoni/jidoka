# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Jidoka** - a Trello-style kanban board operated by an LLM agent with human-in-the-loop approval (the name is the Toyota principle: automation with a human touch). Portfolio project targeting Python AI-agent roles; scope is ~3–4 focused weeks. The interview narrative is "kanban agent with HITL approval, tracing, and evals."

Source material lives in `temp/`: `PROJETO 18.pdf` is the original 2023 spec (Trello + IA; Appwrite, GPT-3.5, react-beautiful-dnd - **all outdated, do not follow it for stack choices**) and `compact.md` is the modernized spec that governs. The PDF is still useful for the wireframe and base data model (columns todo/in-progress/done, card fields, search).

## Repo status

Greenfield monorepo: `frontend/` (Next.js) and `backend/` (FastAPI) are empty scaffolding targets. Planned infra: docker-compose with Postgres + pgvector (Supabase acceptable).

**Build order (deliberate):** scaffold monorepo + docker-compose and get deploy/infra working end-to-end _first_; then implement the agent graph with one tool (`create_task`) fully wired (chat → tool call → DB → board update); UI polish last.

_(Update this file with real build/test/lint commands as scaffolding lands.)_

## Stack (settled - do not relitigate)

- **Frontend:** Next.js 15+ App Router (Server Components + Server Actions), TypeScript, Tailwind v4, shadcn/ui, **dnd-kit** for drag-and-drop (react-beautiful-dnd is deprecated - never use it), Vercel AI SDK for streaming agent events.
- **Zustand only for ephemeral UI state** (drag state, modals, optimistic reorder). Board data is fetched server-side; mutations go through Server Actions.
- **Backend:** Python FastAPI + **LangGraph used directly** - avoid classic LangChain abstractions (chains, AgentExecutor). Postgres + pgvector, LangGraph Postgres checkpointer.
- Backend is deliberately Python even though the frontend is TypeScript - the target jobs are Python AI-agent roles.
- **FastAPI is the single writer to Postgres.** Server Actions never touch the DB directly - they proxy mutations to FastAPI, so manual edits and the agent's `apply` node share the same mutation code paths. The one exception is the chat stream, which the browser consumes directly from a FastAPI SSE endpoint via the Vercel AI SDK.
- **Live board updates are driven by the agent event stream** - no Supabase Realtime, no polling. The `apply` node emits applied-change events on the stream the client is already consuming; the client patches Zustand for the live effect and calls `router.refresh()` to reconcile with server state.
- **Auth is handled in the FastAPI backend** - FastAPI issues and verifies its own JWTs (email/password, OAuth2 password flow is fine for a portfolio project). No Supabase Auth, no Auth.js. Next.js middleware only checks for a valid session token and redirects; all real verification lives in FastAPI, which also keeps the app portable off Supabase-hosted Postgres.
- Observability: **Langfuse tracing** + a **pytest eval suite** asserting correct tool selection/args; results published in the README.

## Agent architecture

The agent is an explicit LangGraph state machine because the feature's control flow _is_ the graph: an agent↔tools loop, `interrupt()` for approval, checkpointed state resumable by `thread_id` (= board_id).

```python
class BoardState(TypedDict):
    messages: Annotated[list, add_messages]
    proposed_changes: list[BoardChange]

g = StateGraph(BoardState)
g.add_node("agent", call_model)      # decides: tools or finish
g.add_node("tools", execute_tools)   # create_task, move_task, ...
g.add_node("propose", build_diff)    # decision = interrupt({"diff": ...})
g.add_node("apply", apply_to_db)
g.add_conditional_edges("agent", route)
g.add_edge("tools", "agent")         # the agent loop
# resume after approval:
# graph.invoke(Command(resume={"approved": True}),
#              config={"configurable": {"thread_id": board_id}})
```

**HITL is the core feature, not an add-on:** the agent never writes to the board directly. Tools accumulate `proposed_changes`; `propose` interrupts with a diff; the user approves/rejects/edits; only `apply` touches the DB.

## Feature scope

0. **Base kanban** - the board is fully usable by hand (create/edit cards, drag across columns via dnd-kit) with no agent involved. Manual mutations go through the same FastAPI endpoints the agent's `apply` node uses.
1. **Chat agent** with tools `create_task`, `move_task`, `breakdown_task`, `prioritize_backlog`, `search_tasks` - actions stream to the UI, cards move live.
2. **HITL approval** - propose→approve→apply diff flow (above).
3. **Paste-to-tickets** - textarea for a syllabus/project brief → structured extraction (Pydantic models `TaskDraft` / `ExtractionResult`) → routed through the _same_ propose→approve flow, reusing `create_task`.
4. **Semantic search** over cards via pgvector.
5. **Evals + tracing** (Langfuse, pytest).
6. **Time tracking** - build incrementally, in this order: (a) each card gets a start/stop button for a pomodoro-style work block, plus manual entry of minutes; work blocks are rows (`task_id`, `started_at`, `ended_at` / `minutes`) so history is kept, not a mutating counter. (b) `Project` is a first-class entity; each task optionally links to one project; time rolls up work block → task → project for a per-project "time invested" view. Time data can later feed `prioritize_backlog` and the standup digest.

Time permitting: standup digest (background job), quiz-me study mode, MCP server exposing the board. Everything else (vision, voice, duplicate detection, cost dashboard, card image uploads from the original PDF) goes in the README roadmap section only - do not implement.

## Gotchas / hard rules

- The extraction prompt must only extract tasks actually present in the pasted text - no inventing tasks.
- Double-pasting the same brief creates duplicate cards; dedupe via embeddings is a later roadmap item, not a blocker.
- Every `tool_use` block must be answered by a matching `tool_result`, or the LLM API returns a 400.
- One `thread_id` per board means one agent conversation per board - concurrent chats on the same board will collide with checkpointed state.

## Design Context

Strategic and visual design context is captured in two root files - read them before building or changing any UI:

- `PRODUCT.md` - register (product), platform (web), audiences (Caio daily-use primary; public users secondary via a no-signup demo space, demo visitor tiebreaks), positioning ("Agent proposes, you decide"), design principles, anti-references (Jira chrome, AI-chatbot-first UI), WCAG 2.1 AA commitment.
- `DESIGN.md` - the visual system ("The Andon Line"): Electric Violet as the sole action/agent accent, andon status tints per column, flat-until-touched elevation, Geist/Geist Mono type roles, named rules and do's/don'ts.
