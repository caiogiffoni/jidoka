# Jidoka

A Trello-style kanban board you can drive by hand or through an LLM agent - with human-in-the-loop approval for every change the agent wants to make.

The name comes from the Toyota principle _jidoka_: automation with a human touch. The agent proposes; you approve, edit, or reject; only then does anything touch the board.

## What it does

- **A real kanban board** - create, edit, and drag cards across columns by hand, like any Trello board. The agent is a layer on top, not the only way in.
- **Chat with your board** - an agent with tools (`create_task`, `move_task`, `breakdown_task`, `prioritize_backlog`, `search_tasks`) that streams its actions to the UI as cards move live.
- **Human-in-the-loop approval** - the agent never writes directly. It builds a diff of proposed changes, execution pauses, and resumes only on your decision.
- **Paste-to-tickets** - paste a syllabus or project brief and get structured task extraction, routed through the same propose → approve flow.
- **Semantic search** over cards via pgvector embeddings.
- **Time tracking** - start a pomodoro-style work block from any card (or log minutes manually) to see how long each task actually took. Tasks link to projects, so time invested rolls up per project.
- **Traced and evaluated** - Langfuse tracing on every agent run, plus a pytest eval suite asserting correct tool selection and arguments. _(Results will be published here.)_

## Stack

| Layer     | Choice                                                                              |
| --------- | ----------------------------------------------------------------------------------- |
| Frontend  | Next.js 15 (App Router), TypeScript, Tailwind v4, shadcn/ui, dnd-kit                |
| Agent     | Python, FastAPI, LangGraph (checkpointed state machine, `interrupt()` for approval) |
| Data      | Postgres + pgvector                                                                 |
| Streaming | SSE from FastAPI, consumed via the Vercel AI SDK                                    |
| Infra     | Docker Compose                                                                      |

The agent is an explicit LangGraph state machine because the feature's control flow _is_ the graph: an agent ↔ tools loop, an interrupt for approval, and checkpointed state resumable per board.

## Data model

Current (SQLModel, in `backend/models.py`):

**`Task`** - one card on the board.

| Field         | Type        | Notes                                             |
| ------------- | ----------- | ------------------------------------------------- |
| `id`          | UUID        | primary key                                       |
| `title`       | str         |                                                   |
| `description` | str \| None |                                                   |
| `column_id`   | str         | `todo` \| `in_progress` \| `done`, indexed        |
| `position`    | int         | display order within the column, kept dense       |
| `created_at`  | datetime    | UTC                                               |

**`WorkBlock`** - one completed pomodoro or manually logged stretch of work on a task. Blocks are append-only rows, not a mutating counter, so history is kept. Timer blocks carry timestamps; manual entries carry only minutes (one of the two is required). Stopped (aborted) focus sessions are never persisted - only a block that finishes is worth keeping.

| Field        | Type             | Notes                                     |
| ------------ | ---------------- | ------------------------------------------ |
| `id`         | UUID             | primary key                               |
| `task_id`    | UUID             | FK → `tasks.id`, cascade delete, indexed  |
| `started_at` | datetime \| None | UTC; set for timer blocks                 |
| `ended_at`   | datetime \| None | UTC; set for timer blocks                 |
| `minutes`    | int \| None      | for manual entry without timestamps       |
| `created_at` | datetime         | UTC                                       |

Planned:

**`Project`** - first-class grouping; each task optionally links to one project (`tasks.project_id`, nullable FK). Time rolls up work block → task → project for a per-project "time invested" view.

| Field  | Type | Notes       |
| ------ | ---- | ----------- |
| `id`   | UUID | primary key |
| `name` | str  |             |

## Status

The base kanban is built and usable by hand: create, edit, and delete cards (confirm dialog + undo toast), drag them across columns with pointer or keyboard (with screen-reader announcements). Mutations are optimistic with rollback and error toasts; the frontend persists through Server Actions to FastAPI, the single writer to Postgres.

A pomodoro timer lives in the header: the classic work / break / long-break cycle, with each focus block linkable to a board task, a repeating alarm that stops when acknowledged, and a daily goal. Work never auto-starts - breaks can. A running countdown survives page reloads, but a block only counts if it finishes while the page is open. A finished focus block linked to a task is persisted as a work-block row; stopped (aborted) sessions are never sent to the backend. Manual minutes entry and the per-project rollup are the next steps of time tracking.

The agent, HITL approval flow, and semantic search are next, in that order.

## Running locally

```bash
docker compose up --watch   # Postgres (pgvector) on :5432, FastAPI on :8000
cd frontend && pnpm install && pnpm dev   # Next.js on :3000
```

The backend can also run outside Docker with `cd backend && uv run fastapi dev main.py` (expects Postgres on `localhost:5432`; override with `DATABASE_URL`).

## Design workflow

UI work is governed by two design-context files checked into the repo, enforced by design skills for coding agents (currently `emil-design-eng` and `frontend-design` in `.claude/skills/`):

- **`PRODUCT.md`** - the strategic layer: register, audiences, positioning ("agent proposes, you decide"), anti-references, and a WCAG 2.1 AA commitment.
- **`DESIGN.md`** - the visual system ("The Andon Line"): one Electric Violet accent reserved for action and agent activity, per-column andon status tints, flat-until-touched elevation, and named rules that keep agent-generated UI on-brand.

The context files were bootstrapped with **impeccable**: `/impeccable init` captured the strategy and visual system, `/impeccable audit board` scored the board 13/20 and produced a prioritized backlog, the P1s were fixed (keyboard drag-and-drop with screen-reader announcements, visible focus, error toasts with optimistic rollback, AA contrast on tinted surfaces), and `/impeccable polish board` swept the rest (reduced-motion support, labeled forms, doctrine cleanup). Every fix was verified live in the browser in both themes.

## Roadmap

- Standup digest (background job)
- Quiz-me study mode over board content
- MCP server exposing the board to other agents
- Duplicate-card detection via embeddings
- Card attachments / vision, voice input, cost dashboard
