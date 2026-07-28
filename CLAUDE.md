# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**Jidoka** - a Trello-style kanban board operated by an LLM agent with human-in-the-loop approval (the name is the Toyota principle: automation with a human touch). Portfolio project targeting Python AI-agent roles; scope is ~3-4 focused weeks. The interview narrative is "kanban agent with HITL approval, tracing, and evals."

Source material lives in `temp/`: `PROJETO 18.pdf` is the original 2023 spec (Trello + IA; Appwrite, GPT-3.5, react-beautiful-dnd - **all outdated, do not follow it for stack choices**) and `compact.md` is the modernized spec that governs. The PDF is still useful for the wireframe and base data model (columns todo/in-progress/done, card fields, search).

## Repo status

Monorepo with the base kanban (feature 0) built and working:

- `backend/` - FastAPI + SQLModel. Endpoints: `GET /health`, `GET /tasks` (`?include_archived=true` to include archived tasks, excluded by default), `POST /tasks`, `PATCH /tasks/{id}` (title/description/project_id/checklist/due_date, full replace), `PATCH /tasks/{id}/move`, `PATCH /tasks/{id}/archive`, `DELETE /tasks/{id}`, `POST`/`GET /tasks/{id}/work-blocks`, `POST`/`GET /projects`, `PATCH`/`DELETE /projects/{id}` (full replace, including `daily_enabled`/`daily_template`), `POST /projects/daily-tasks/generate`, `GET /work-blocks/stats/daily`. Move, archive, and delete all reindex the affected column(s) so positions stay dense; deleting a task cascade-deletes its work blocks; deleting a project sets its tasks' `project_id` to null (`ON DELETE SET NULL`) rather than deleting or blocking deletion of the tasks. No migration tool (no Alembic ever) - schema changes to an existing local DB need a manual `ALTER TABLE` or a volume wipe, since `create_all()` only creates missing tables.
- `frontend/` - Next.js, two routes: `/` is the projects + weekly time dashboard (see below), `/board` is the kanban board. Board: dnd-kit drag across columns (pointer + keyboard with SR announcements), create dialog, task detail/edit dialog, delete with confirm dialog + undo toast. Mutations are optimistic in Zustand with rollback + error toast on server failure; persistence goes through Server Actions (`src/app/actions.ts`) → FastAPI.
- Backlog column + task archiving - `ColumnId` has a fourth value, `backlog`, ordered before `todo`; its status dot is neutral gray rather than a fourth andon hue, since it marks "not queued" rather than a station on the line (`DESIGN.md`). Any task can be archived instead of deleted (`Task.archived`, default `false`, `PATCH /tasks/{id}/archive`) - archiving/unarchiving reindexes column positions the same way move/delete do, and an unarchived task re-appends to the end of its column rather than returning to its old slot. Frontend: an archive icon in the task dialog (`archive-task.tsx`), same optimistic-remove + undo-toast shape as delete (`delete-task.tsx`) - no confirm dialog, since undo is the safety net and archiving isn't destructive. Known gap, deliberate: no UI to browse or restore archived tasks once the undo toast closes.
- Pomodoro timer - tomato button in the board header opens a popover: countdown, task select (links the block to a board task), start/pause/resume/stop, gear → settings dialog. State in `stores/pomodoro-store.ts` (settings/counts persisted to localStorage as `jidoka-pomodoro`); alarm sounds synthesized in `lib/alarm.ts` (no audio assets). Focus blocks linked to a task persist to the backend as `work_blocks` rows via `POST /tasks/{id}/work-blocks`. See "Pomodoro behavior" below.
- Projects + weekly dashboard (`/`, the app's landing route) - create projects (name only), and see a 7-day stacked bar chart of `work_blocks` minutes broken down by day and by project, with a "Not defined" bucket for tasks with no project. Chart is hand-rolled SVG/HTML (no chart library dependency) in `components/projects/`; colors come from a validated 4-hue categorical palette (`lib/project-palette.ts`) distinct from Electric Violet and the andon status hues - derived client-side from each project's position in the `created_at`-ordered list, not a persisted field. A task can be linked to a project at creation (the "Add task" dialog's optional Project select) or reassigned later from the task detail dialog's edit mode (same Project select, wired via `PATCH /tasks/{id}`). Each project row on `/` also shows its linked tasks' counts by board column (`lib/project-task-counts.ts`, computed client-side from the same task fetch, no new endpoint). The two pages cross-link via a header icon-button (dashboard ↔ board).
- Card checklists - any task can hold a Trello-style checklist (`Task.checklist`, a JSON column of `{text, checked}` items), settable at creation (`AddTaskDialog`) or edited straight from `TaskDialog`'s view mode (no edit-mode step) via `PATCH /tasks/{id}` (full replace - callers always pass the current checklist alongside title/description/project_id/due_date so an unrelated edit can't wipe it), optimistic in Zustand with rollback + toast on failure. Progress (e.g. "2/4") shows on the board card face (`task-card.tsx`) whenever a checklist is non-empty. The add/remove-row list editor is shared (`components/checklist-item-editor.tsx`) between `AddTaskDialog` and the daily-task template popup below.
- Due dates - `Task.due_date` (plain `date`, no time component), editable via a native date input in `TaskDialog`'s edit form (next to Project). A card overdue (`due_date` in the past and column isn't `done`) renders its Due badge/card-face indicator with the `destructive` (Alarm Red) tint; otherwise neutral. Deliberately two-state, not three - `DESIGN.md`'s Andon Rule reserves amber/sky/emerald for the column-header dot only, so there's no separate "due soon" color. Helpers in `lib/due-date.ts`.
- Markdown formatting toolbar - `components/markdown-toolbar.tsx`, shared by `TaskDialog` and `ProjectDialog`'s description editors. Bold/italic/list/link buttons wrap or prefix the current `<textarea>` selection with Markdown syntax (no rich-text/WYSIWYG dependency, since descriptions are stored and rendered as plain Markdown via `MarkdownText`) plus a formatting-help popover. Required adding `ref` support to `components/ui/textarea.tsx` (React 19 ref-as-prop, no `forwardRef`).
- Daily project tasks - a project can enable "Generate a daily task" (checkbox), either at creation (`CreateProjectDialog`) or later (`ProjectDialog`'s edit form). Checking it opens `components/projects/daily-template-dialog.tsx`, a popup that mirrors the real "Add task" dialog exactly (Title, Description, Checklist, Project, Column) per the user's ask - but Project/Column are disabled/display-only (a generated card always belongs to this project and always lands in `todo`), and it never calls the task API: "Save template" hands `{title, description, checklist}` back to the project form, so nothing appears on the board until the next generation. `title` is optional - the generated card is always named `Daily - DD-MM-YY - <project>`, with the template's title (if any) appended, not substituted in. Cancelling before ever saving reverts the checkbox if no template exists yet. Once saved, the project row shows a read-only title (if set) + checklist preview and an "Edit template" button to reopen it prefilled. `DailyTaskGenerator` (mounted in the root layout) fires once per browser-local day and calls the `generateDailyTasks` server action → `POST /projects/daily-tasks/generate`, which builds that title and uses the template's description/checklist directly (idempotent per UTC day). See "Feature scope" item 8 for the known trigger-mechanism caveat (no real login exists yet) and its title-format history.
- `compose.yaml` - pgvector (pg17) + backend with `docker compose watch` sync. The frontend is **not** containerized; run it with pnpm.

**Known gaps:** task delete is deferred: the server `DELETE` fires only when the undo toast closes, so closing the tab during the toast drops the delete (deliberate - favors keeping data).

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

```bash
docker compose up -d db          # Postgres needs to be reachable on :5432
cd backend && uv run pytest -v   # backend suite, backend/tests/
cd frontend && pnpm test         # Vitest, no backend/Postgres needed
```

`backend/tests/` exercises the FastAPI endpoints against a real Postgres, each test in a transaction rolled back afterward so it never leaves data behind; runs in CI on any push/PR touching `backend/` (`.github/workflows/backend-tests.yml`). Frontend Vitest tests run in CI the same way for `frontend/` (`.github/workflows/frontend-tests.yml`). `TESTING.md` is the manual test script (numbered steps, checkboxes marking which also have automated coverage) for everything not yet automated, plus the full frontend click-through. The pytest **eval** suite (tool-selection/argument assertions against the agent) is separate and still arrives with the agent.

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
6. **Time tracking** - build incrementally, in this order: (a) done - each card's pomodoro focus blocks persist as `work_blocks` rows (`task_id`, `started_at`, `ended_at` / `minutes`); manual minutes-only entry is supported by the model/endpoint but has no UI yet. (b) done - `Project` is a first-class entity (name only - no persisted color; the frontend derives chart color from each project's position in the `created_at`-ordered list, so colors aren't a stable per-project identity); tasks link to one at creation or reassign later via the task dialog's edit mode; time rolls up work block → task → project in the weekly dashboard at `/`. Still open: feeding this data into `prioritize_backlog`/the standup digest.
7. **Card checklists** - done. Any `Task` can hold a Trello-style checklist (`checklist: list[{text, checked}]`, JSON column), settable at creation (`AddTaskDialog`) or edited straight from `TaskDialog`'s view mode - check/uncheck, add, remove - each change a full-replace `PATCH /tasks/{id}` call, optimistic in Zustand with rollback on failure. Progress shows on the board card face.
8. **Daily project tasks** - done. A `Project` can hold an editable daily template (`daily_enabled: bool`, `daily_template: {title, description, checklist} | None` - a nested `DailyTemplate` model in a JSON column, not just a plain checklist list), settable at creation or later via edit. Authored through a popup that mirrors the real "Add task" dialog (`DailyTemplateDialog`) rather than a bespoke inline list, per the user's explicit ask to reuse that exact UI - Project/Column in that popup are disabled/display-only, since a generated card always belongs to the project it came from and always lands in `todo`. `title` on the template is optional - `POST /projects/daily-tasks/generate` always names the card `Daily - DD-MM-YY - <project>` and appends ` - <template.title>` only if one was given, using the template's description/checklist directly either way (idempotent via `daily_last_generated`) - no chatbot UI. Title format history: started as `daily-DD-MM-YYYY-<project>`, then `Daily - DD-MM-YY - <project>`, briefly became `<template.title> - DD-MM-YY` when title was made a required field, now back to `Daily - DD-MM-YY - <project>` with the title appended and optional, since a mandatory title added least-value for the effort it cost elsewhere. Trigger is a placeholder: `DailyTaskGenerator` (mounted in the root layout) fires once per browser-local day via a `localStorage` gate, since there's no real login event yet - revisit once auth ships. (This feature went through one reverted false start - a task-level design where any task could be a daily template, corrected back to project-level via an uncommitted `git checkout` - and two later redesigns, all clarified with AskUserQuestion before writing code once the pattern was learned.)

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

## Git workflow

- **Never commit on the user's behalf.** The user always commits manually. Do not
  run `git commit`, `git push`, `git reset`, `git rebase`, or any other git
  mutation unless explicitly asked. Inspecting status/diff to help the user
  understand what changed is fine.
