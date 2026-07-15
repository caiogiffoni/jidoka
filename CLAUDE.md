# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Jidoka** - a Trello-style kanban board operated by an LLM agent with human-in-the-loop approval (the name is the Toyota principle: automation with a human touch). Portfolio project targeting Python AI-agent roles; scope is ~3–4 focused weeks. The interview narrative is "kanban agent with HITL approval, tracing, and evals."

Source material lives in `temp/`: `PROJETO 18.pdf` is the original 2023 spec (Trello + IA; Appwrite, GPT-3.5, react-beautiful-dnd - **all outdated, do not follow it for stack choices**) and `compact.md` is the modernized spec that governs. The PDF is still useful for the wireframe and base data model (columns todo/in-progress/done, card fields, search).

## Repo status

Monorepo with the base kanban (feature 0) built and working:

- `backend/` - FastAPI + SQLModel. Endpoints: `GET /health`, `GET /tasks`, `POST /tasks`, `PATCH /tasks/{id}/move`, `DELETE /tasks/{id}`, `POST`/`GET /tasks/{id}/work-blocks`. Move and delete reindex the affected column(s) so positions stay dense; deleting a task cascade-deletes its work blocks.
- `frontend/` - Next.js board: dnd-kit drag across columns (pointer + keyboard with SR announcements), create dialog, task detail/edit dialog, delete with confirm dialog + undo toast. Mutations are optimistic in Zustand with rollback + error toast on server failure; persistence goes through Server Actions (`src/app/actions.ts`) → FastAPI.
- Pomodoro timer - tomato button in the header opens a popover: countdown, task select (links the block to a board task), start/pause/resume/stop, gear → settings dialog. State in `stores/pomodoro-store.ts` (settings/counts persisted to localStorage as `jidoka-pomodoro`); alarm sounds synthesized in `lib/alarm.ts` (no audio assets). Focus blocks linked to a task persist to the backend as `work_blocks` rows via `POST /tasks/{id}/work-blocks`. See "Pomodoro behavior" below.
- `compose.yaml` - pgvector (pg17) + backend with `docker compose watch` sync. The frontend is **not** containerized; run it with pnpm.

**Known gaps:** task title/description edits in the task dialog only update the Zustand store - there is no `PATCH /tasks/{id}` endpoint yet, so edits don't persist. Delete is deferred: the server `DELETE` fires only when the undo toast closes, so closing the tab during the toast drops the delete (deliberate - favors keeping data).

**Build order (deliberate):** infra + base kanban first (done); next, the agent graph with one tool (`create_task`) fully wired (chat → tool call → DB → board update); UI polish last.

### Commands

```bash
docker compose up --watch        # Postgres (pgvector) :5432 + backend :8000
cd backend && uv run fastapi dev main.py   # backend alone (DATABASE_URL defaults to localhost:5432)
cd frontend && pnpm dev          # Next.js :3000 (expects backend on :8000, BACKEND_URL to override)
cd frontend && pnpm lint         # eslint
cd frontend && npx tsc --noEmit  # typecheck
cd frontend && pnpm build        # production build
```

No test suites yet (the pytest eval suite arrives with the agent).

`HISTORY.md` at the repo root is a running session log (newest first). At the end of a working session, append a dated entry: what landed, decisions made, what's next.

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

### Pomodoro behavior (settled)

The timer follows the classic pomodoro cycle:

1. **Work** (default 25 min) - press Start to begin. Completing a work session counts as one pomodoro.
2. **Break** (default 5 min) - follows each work session. Every 4th pomodoro (configurable, "long break every") earns a **long break** (default 15 min) instead.
3. Back to idle - when a break ends, the next work session is **never** auto-started; the user may be away from the keyboard, so work always requires a manual Start.

Breaks can start automatically after work ends (auto-start break, on by default) or wait to be started. The alarm repeats every "repeat alarm every" seconds until acknowledged - any timer interaction, including opening the popover, counts - and an unacknowledged alarm gives up on its own after "stop alarm after" (default 3 min; the spec scoped this to break alarms, but it is applied to all alarms so nothing can ring forever).

**Pause/Resume** freezes the current phase and picks it back up. **Stop** aborts the phase and returns to idle - a stopped work session never counts toward stats, streaks, or the daily goal, and is **not** persisted: only a focus block that actually finishes is worth keeping as history. A finished focus block linked to a task is saved as a `work_blocks` row; blocks with no task selected have nowhere to attach and stay client-side. A failed save shows an error toast but never disturbs the timer.

The full timer state (status, phase, absolute `endsAt`) persists to localStorage, so a running countdown survives reloads: `endsAt` is an absolute timestamp, so after a refresh the remaining time is still exact. **A block only counts if it finishes with the page open** - if the countdown expired while the page was closed, `catchUp()` (run on load) discards it entirely: no stats, no daily goal, no alarm, no POST - the user may not have been working after closing the tab. Rehydration is explicit on mount (`skipHydration`) to avoid SSR hydration mismatches in the header button. The work-block POST (`persistFocusBlock` in `pomodoro-store.ts`, fire-and-forget through the `recordWorkBlock` Server Action) fires only from `finishPhase()`, on a live focus-block finish. Known limit: two open tabs both run the clock and would double-count.

## Gotchas / hard rules

- **Avoid Claude in Chrome browser automation - it burns a lot of tokens.** Verify changes with `curl` against FastAPI (`:8000`) and `docker exec jidoka-db-1 psql -U jidoka -d jidoka` for data checks instead. Only reach for the browser when the user asks or a change genuinely can't be confirmed any other way, and keep the session minimal.
- The extraction prompt must only extract tasks actually present in the pasted text - no inventing tasks.
- Double-pasting the same brief creates duplicate cards; dedupe via embeddings is a later roadmap item, not a blocker.
- Every `tool_use` block must be answered by a matching `tool_result`, or the LLM API returns a 400.
- One `thread_id` per board means one agent conversation per board - concurrent chats on the same board will collide with checkpointed state.

## Design Context

Strategic and visual design context is captured in two root files - read them before building or changing any UI:

- `PRODUCT.md` - register (product), platform (web), audiences (Caio daily-use primary; public users secondary via a no-signup demo space, demo visitor tiebreaks), positioning ("Agent proposes, you decide"), design principles, anti-references (Jira chrome, AI-chatbot-first UI), WCAG 2.1 AA commitment.
- `DESIGN.md` - the visual system ("The Andon Line"): Electric Violet as the sole action/agent accent, andon status tints per column, flat-until-touched elevation, Geist/Geist Mono type roles, named rules and do's/don'ts.
