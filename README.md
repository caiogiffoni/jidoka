# Jidoka

A Trello-style kanban board you can drive by hand or through an LLM agent - with human-in-the-loop approval for every change the agent wants to make.

The name comes from the Toyota principle _jidoka_: automation with a human touch. The agent proposes; you approve, edit, or reject; only then does anything touch the board.

## What it does

- **A real kanban board** - create, edit, and drag cards across columns by hand, like any Trello board. The agent is a layer on top, not the only way in.
- **Backlog column + archiving** - a Backlog column sits before To Do for work that isn't queued yet, and any card can be archived (hidden from the board, not deleted) with the same confirm-free undo-toast safety net as delete.
- **Card checklists** - any card can hold a Trello-style checklist, added at creation or afterward: check items off, add or remove them, and see progress (e.g. "2/4") right on the card face.
- **Due dates** - set an optional due date on any card; overdue cards get a quiet red badge, both in the card dialog and on the card face.
- **Markdown formatting toolbar** - bold, italic, lists, and links, one click each, on any description field.
- **Chat with your board** - an agent with tools (`create_task`, `move_task`, `breakdown_task`, `prioritize_backlog`, `search_tasks`) that streams its actions to the UI as cards move live.
- **Human-in-the-loop approval** - the agent never writes directly. It builds a diff of proposed changes, execution pauses, and resumes only on your decision.
- **Paste-to-tickets** - paste a syllabus or project brief and get structured task extraction, routed through the same propose → approve flow.
- **Semantic search** over cards via pgvector embeddings.
- **Time tracking** - start a pomodoro-style work block from any card to see how long each task actually took. Tasks optionally link to a project, and a dashboard rolls time up per project with a 7-day stacked-bar chart.
- **Daily project tasks** - opt a project into a daily template - an optional title, description, and checklist, drafted in a popup that looks just like creating a real task - at creation or later; a fresh card cloned from that template is generated automatically once a day for every opted-in project, named after the project and date.
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

| Field         | Type                       | Notes                                             |
| ------------- | -------------------------- | -------------------------------------------------- |
| `id`          | UUID                       | primary key                                       |
| `title`       | str                        |                                                    |
| `description` | str \| None                |                                                    |
| `column_id`   | str                        | `backlog` \| `todo` \| `in_progress` \| `done`, indexed |
| `project_id`  | UUID \| None               | FK → `projects.id`, `ON DELETE SET NULL`, indexed |
| `position`    | int                        | display order within the column, kept dense       |
| `archived`    | bool                       | default `false`, indexed; excluded from `GET /tasks` unless `?include_archived=true` |
| `checklist`   | list[{text, checked}]      | JSON column; a Trello-style checklist on the card |
| `due_date`    | date \| None                | optional; overdue → red badge (not `done`)        |
| `created_at`  | datetime                   | UTC                                               |

**`WorkBlock`** - one completed pomodoro or manually logged stretch of work on a task. Blocks are append-only rows, not a mutating counter, so history is kept. Timer blocks carry timestamps; manual entries carry only minutes (one of the two is required). Stopped (aborted) focus sessions are never persisted - only a block that finishes is worth keeping.

| Field        | Type             | Notes                                     |
| ------------ | ---------------- | ------------------------------------------ |
| `id`         | UUID             | primary key                               |
| `task_id`    | UUID             | FK → `tasks.id`, cascade delete, indexed  |
| `started_at` | datetime \| None | UTC; set for timer blocks                 |
| `ended_at`   | datetime \| None | UTC; set for timer blocks                 |
| `minutes`    | int \| None      | for manual entry without timestamps       |
| `created_at` | datetime         | UTC                                       |

**`Project`** - first-class grouping; each task optionally links to one project (`tasks.project_id`, nullable FK, `ON DELETE SET NULL` - deleting a project unlinks its tasks rather than deleting them). Time rolls up work block → task → project for the weekly dashboard. Chart color isn't a DB field - the frontend derives it from each project's position in the `created_at`-ordered list (`lib/project-palette.ts`), so colors aren't a stable per-project identity.

| Field                   | Type          | Notes                                                              |
| ----------------------- | ------------- | -------------------------------------------------------------------- |
| `id`                    | UUID          | primary key                                                        |
| `name`                  | str           |                                                                     |
| `description`           | str \| None   | optional, rendered as Markdown                                     |
| `created_at`            | datetime      | UTC                                                                 |
| `daily_enabled`         | bool                                | default `false` - opts the project into daily task generation |
| `daily_template`        | {title, description, checklist} \| None | JSON column; cloned into a real card once a day - `None` until drafted |
| `daily_last_generated`  | str \| None                         | UTC `YYYY-MM-DD`; guards against generating twice in the same day |

## Status

The base kanban is built and usable by hand: create, edit, and delete cards (confirm dialog + undo toast), drag them across columns with pointer or keyboard (with screen-reader announcements). Mutations are optimistic with rollback and error toasts; the frontend persists through Server Actions to FastAPI, the single writer to Postgres.

A Backlog column sits before To Do, with a neutral gray status dot rather than a fourth andon color - it marks work that isn't queued yet, not a stage of work in progress. Any card can also be archived instead of deleted, from an icon in its detail dialog: it disappears from the board immediately behind the same undo-toast pattern as delete, but there's deliberately no confirm dialog (archiving isn't destructive) and no UI yet to browse or restore archived cards once the toast closes.

Any card can carry a checklist - drafted right in the "Add task" form, or added later from the task detail dialog's view mode with no need to enter edit mode first. Check an item, add one, or remove one and it saves immediately (optimistic, with rollback and a toast if the save fails); the board card face shows a quiet progress count (e.g. "2/4") whenever a card has one.

Any card can also get a due date (edit mode, next to Project) and any description field gets a small Markdown toolbar - bold, italic, bulleted/numbered list, link, and a formatting cheatsheet - that wraps or prefixes the current text selection rather than rendering rich text (descriptions stay plain Markdown under the hood). An overdue card - past its due date and not in Done - gets a quiet red badge, on the card face and in the dialog; there's deliberately no separate "due soon" color, since the design system reserves its status hues for the column dot alone.

A pomodoro timer lives in the board header: the classic work / break / long-break cycle, with each focus block linkable to a board task, a repeating alarm that stops when acknowledged, and a daily goal. Work never auto-starts - breaks can. A running countdown survives page reloads, but a block only counts if it finishes while the page is open. A finished focus block linked to a task is persisted as a work-block row; stopped (aborted) sessions are never sent to the backend.

A projects + weekly time dashboard lives at `/` (the kanban board moved to `/board`): create projects, each with an optional Markdown description, and see the last 7 days of focus time as a stacked bar chart broken down by day and by project, with a "Not defined" bucket for tasks with no project. Each project row also shows its linked tasks' counts by board column (To Do / In Progress / Done). A task can link to a project at creation via the "Add task" dialog, or be reassigned later from the task detail dialog's edit mode. That dialog also renders a task's description as Markdown, shows the project it's linked to and the total time logged against it, and supports manual minutes entry independent of the pomodoro timer.

Any project can opt into daily tasks via a "Generate a daily task" checkbox, available both when creating the project and later from its edit dialog. Checking it opens a popup that looks just like the real "Add task" dialog - Title, Description, Checklist, even Project and Column shown for visual consistency, though the latter two are fixed (a generated card always belongs to this project and always lands in To Do). Title is optional too: the generated card is always named "Daily - DD-MM-YY - \<project\>", with the template's title appended only if you gave it one, not replacing it. "Save template" saves it back into the project's own form rather than the board, so nothing shows up immediately. Once a day, that named card is generated in To Do with the template's description and checklist, for every opted-in project - idempotent per UTC day, so it's safe to trigger more than once. There's no real login system yet, so "once a day" is approximated client-side (fires on first app load per browser-local day) rather than tied to an actual sign-in event; that will move to the real login/session-start event once auth ships.

The agent, HITL approval flow, and semantic search are next, in that order.

## Running locally

```bash
docker compose up --watch   # Postgres (pgvector) on :5432, FastAPI on :8000
cd frontend && pnpm install && pnpm dev   # Next.js on :3000
```

The backend can also run outside Docker with `cd backend && uv run fastapi dev main.py` (expects Postgres on `localhost:5432`; override with `DATABASE_URL`).

## Testing

```bash
docker compose up -d db          # Postgres needs to be reachable on :5432
cd backend && uv run pytest -v

cd frontend && pnpm test          # Vitest, no backend/Postgres needed
```

The suite in `backend/tests/` exercises the FastAPI endpoints against a real Postgres - each test runs inside a transaction that's rolled back afterward, so it never leaves data in the dev database. It runs automatically in CI (`.github/workflows/backend-tests.yml`) on any push or PR touching `backend/`.

## Backlog

Deliberately deferred engineering follow-ups:

- **Frontend E2E tests **
- **Daily task trigger** - move off the client-side "first load per day" approximation onto the real login/session-start event once auth ships

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
- Local-day bucketing for the weekly dashboard chart (`GET /work-blocks/stats/daily` currently buckets by UTC calendar day since timestamps are stored in UTC; work logged late at night in a non-UTC timezone can land on the wrong day)
