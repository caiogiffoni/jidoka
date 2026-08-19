# AGENTS.md — Jidoka

This file is a concise orientation for AI coding agents working on **Jidoka**.
Jidoka is a Trello-style kanban board operated by hand or by an LLM agent, with
human-in-the-loop (HITL) approval for every agent-originated change. The name
comes from the Toyota principle: automation with a human touch.

The project language (comments, docs, commit messages) is **English**.

---

## 1. Project overview

- **Goal:** A usable kanban board whose main differentiator is an AI agent that
  proposes changes as a diff and waits for human approval before touching the
  board.
- **Current status:** The base kanban is built and working by hand. The agent,
  HITL approval flow, semantic search, and full eval/tracing stack are planned
  next.
- **Repo type:** Monorepo with two main packages:
  - `backend/` — FastAPI + SQLModel + Postgres/pgvector (Python 3.14)
  - `frontend/` — Next.js 16 App Router + TypeScript + Tailwind v4 + shadcn/ui
- **Infra (local):** Docker Compose (`compose.yaml`) for Postgres + backend;
  frontend runs locally with pnpm (not containerized).
- **Infra (production):** Frontend on Vercel; backend + Postgres on a single
  AWS EC2 `t4g.micro` in `us-east-1`, orchestrated with Docker Compose
  (`compose.prod.yaml`) behind nginx + Certbot. Deploy pipeline is GitHub
  Actions → GHCR → AWS Systems Manager Run Command.

Source material in `temp/`:
- `PROJETO 18.pdf` — original 2023 spec (outdated stack; do not follow for
  implementation decisions).
- `compact.md` — modernized spec that governs current work.

---

## 2. Technology stack

| Layer | Choice |
|-------|--------|
| Frontend framework | Next.js 16 (App Router), React 19, TypeScript 5 |
| Styling | Tailwind CSS v4, shadcn/ui (`components.json` style: `radix-nova`) |
| Fonts | Geist (UI), Geist Mono (data/numbers) via `next/font/google` |
| Drag-and-drop | @dnd-kit/core + sortable (react-beautiful-dnd is deprecated — never use it) |
| State | Zustand for ephemeral UI state only; board data is server-fetched |
| Backend | Python 3.14, FastAPI, SQLModel, Pydantic |
| Database | Postgres 17 with pgvector extension |
| DB driver | psycopg 3 (binary) |
| Python env / deps | uv (`pyproject.toml`, `uv.lock`) |
| Package manager (frontend) | pnpm (`package.json`, `pnpm-lock.yaml`) |
| Testing backend | pytest + FastAPI `TestClient` against real Postgres |
| Testing frontend | Vitest + React Testing Library + jsdom |
| CI/CD | GitHub Actions (`.github/workflows/backend-tests.yml`, `frontend-tests.yml`, `deploy.yml`) |
| Container runtime (local) | Docker Compose (`compose.yaml`) |
| Container runtime (prod) | Docker Compose (`compose.prod.yaml`) on AWS EC2 |
| Reverse proxy / TLS (prod) | nginx + Certbot |
| Production deploy | GitHub Actions → GHCR → AWS Systems Manager Run Command |

Planned but not yet implemented: LangGraph agent graph, Langfuse tracing,
Vercel AI SDK streaming, JWT auth in FastAPI, MCP server.

---

## 3. Project structure

```
.
├── backend/
│   ├── main.py              # FastAPI app, all HTTP endpoints
│   ├── models.py            # SQLModel table + request/response models
│   ├── db.py                # SQLAlchemy engine + session helper
│   ├── pyproject.toml       # Python deps + pytest config
│   ├── uv.lock              # Locked dependency graph
│   ├── Dockerfile           # Production-ish backend image
│   └── tests/               # pytest suite
├── frontend/
│   ├── src/
│   │   ├── app/             # Next.js App Router pages + Server Actions
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx     # Dashboard route: / (projects + weekly chart)
│   │   │   ├── board/page.tsx # Kanban route: /board
│   │   │   ├── actions.ts   # All Server Actions (proxy to FastAPI)
│   │   │   └── globals.css  # Tailwind entry + design tokens
│   │   ├── components/
│   │   │   ├── board/       # Kanban-specific components
│   │   │   ├── projects/    # Dashboard-specific components
│   │   │   ├── pomodoro/    # Timer components
│   │   │   ├── ui/          # shadcn/ui base components
│   │   │   └── *.tsx        # Shared components (theme, markdown, etc.)
│   │   ├── lib/             # Pure helpers + types + API client helpers
│   │   └── stores/          # Zustand stores (board, pomodoro)
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── eslint.config.mjs
│   ├── vitest.config.ts
│   └── vitest.setup.ts
├── compose.yaml             # Docker Compose: pgvector + backend (local dev)
├── compose.prod.yaml        # Production Docker Compose: nginx + Certbot + backend + pgvector
├── nginx.conf               # Production nginx reverse-proxy config
├── deploy-ec2.md            # Step-by-step production deployment checklist
├── README.md                # User-facing overview + data model
├── CLAUDE.md                # Claude Code specific guidance (read it)
├── DESIGN.md                # Visual design system ("The Andon Line")
├── PRODUCT.md               # Product positioning, audience, principles
├── TESTING.md               # Manual test plan (numbered steps)
└── HISTORY.md               # Running session log (newest first)
```

---

## 4. Build, run, and lint commands

### Backend

```bash
# Run backend + Postgres via Docker Compose (recommended for local dev)
docker compose up --watch          # Postgres :5432, backend :8000, auto-reload on change

# Run backend alone (expects Postgres on localhost:5432; override with DATABASE_URL)
cd backend && uv run fastapi dev main.py

# Install / sync dependencies
cd backend && uv sync --locked
```

### Frontend

```bash
cd frontend && pnpm install        # install deps
cd frontend && pnpm dev            # Next.js dev server :3000
cd frontend && pnpm build          # production build
cd frontend && pnpm lint           # ESLint (eslint-config-next)
cd frontend && npx tsc --noEmit    # typecheck
```

### Environment variables

- `DATABASE_URL` — Postgres connection string for the backend.
  Default: `postgresql+psycopg://jidoka:jidoka@localhost:5432/jidoka`
- `BACKEND_URL` — URL the frontend Server Actions use to reach FastAPI.
  Default: `http://localhost:8000`

---

## 5. Testing strategy

### Test principles

- Every new function gets a test. Bug fixes get a regression test.
- Mock external I/O (API, DB, filesystem) with named fake classes, not inline
  stubs.
- Tests must be F.I.R.S.T: fast, independent, repeatable, self-validating,
  timely.

### Backend tests

- Framework: pytest.
- Location: `backend/tests/`.
- Strategy: every test runs against a real Postgres inside a transaction that
  is rolled back afterward (`conftest.py`). No separate test database required.
- Run:

```bash
docker compose up -d db            # ensure Postgres is reachable on :5432
cd backend && uv run pytest -v
```

- CI: `.github/workflows/backend-tests.yml` runs on pushes/PRs touching
  `backend/**`.

### Frontend tests

- Framework: Vitest + React Testing Library + jsdom.
- Location: co-located with source (e.g. `*.test.ts`, `*.test.tsx`).
- Run:

```bash
cd frontend && pnpm test
```

- CI: `.github/workflows/frontend-tests.yml` runs on pushes/PRs touching
  `frontend/**`.

### Manual testing

- `TESTING.md` is the manual test plan. Steps are numbered (B1-B69 for backend,
  F1-F17 for frontend). Checkboxes mark steps that also have automated pytest
  coverage.
- Many frontend interactions (drag-and-drop, theme toggling, undo toasts,
  pomodoro timer) are currently manual only.

---

## 6. Code style and conventions

### General

- **Minimal changes:** make the smallest change that satisfies the requirement.
  Do not opportunistically refactor unrelated code.
- **Match existing code:** follow the comment density, naming, and structure of
  the file you are editing.
- **English** for all code comments, docstrings, docs, and commit messages.

### Backend conventions

- Python 3.14 syntax is acceptable (e.g. `str | None`).
- Models live in `backend/models.py`; endpoints live in `backend/main.py`.
- SQLModel is used for both tables and Pydantic request/response models.
- `PATCH /tasks/{id}` and `PATCH /projects/{id}` are **full replaces**, not
  partial patches. Callers must carry the entire current state (including
  `checklist` / `daily_template`) or the omitted fields are wiped.
- `create_db_and_tables()` is called on app startup; there is **no migration
  tool** (no Alembic). Schema changes to an existing local DB require manual
  `ALTER TABLE` or a volume wipe.
- Endpoints return proper HTTP status codes (`201` for creates, `204` for
  deletes, `404` for missing resources, `422` for validation errors).
- Helper naming: `get_task_or_404`, `get_project_or_404`.

### Frontend conventions

- **Server Components by default** for data fetching (`page.tsx` files fetch
  from FastAPI).
- **Server Actions** (`src/app/actions.ts`) are the only mutation path from the
  frontend; they proxy to FastAPI. The browser never calls the backend directly
  except for the future agent event stream.
- **Zustand** is for ephemeral UI state only (drag state, dialogs, optimistic
  reorder, pomodoro timer). Persistent board data lives on the server.
- Components are grouped by feature under `src/components/`:
  - `board/` — kanban
  - `projects/` — dashboard
  - `pomodoro/` — timer
  - `ui/` — shadcn base components
- Use `@/` path alias for imports from `src/`.
- Tailwind classes should respect the design tokens in `globals.css`; design
  details live in `DESIGN.md`.

### Clean Code and SOLID guidelines

Write code that is easy to read, test, and change. Follow Clean Code and SOLID
principles pragmatically — never as an excuse to over-engineer or refactor
unrelated code.

**Code style**

- Functions: aim for 4–20 lines. Split if longer.
- Files: keep under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific and unique. Avoid generic names like `data`, `handler`,
  `Manager`. Prefer names that return fewer than five grep hits in the codebase.
- Types: explicit. Avoid `any`, untyped `Dict`, and untyped functions.
- No code duplication. Extract shared logic into a function or module.
- Early returns over nested `if`s. Max two levels of indentation.
- Exception messages must include the offending value and expected shape.
- Avoid magic strings and numbers. Reuse constants and enums (e.g., column IDs).
- Leave the code cleaner than you found it within the scope of your change, but
  do not opportunistically refactor files you are not touching.

**SOLID**

- **Single Responsibility Principle (S):** each module, class, and function
  should have one reason to change. Keep DB logic in services, HTTP logic in
  routers, LLM tool schemas in `tools.py`, and graph orchestration in
  `graph.py`.
- **Open/Closed Principle (O):** extend behavior by adding new types or tools,
  not by editing existing flows. For example, new agent mutations should add a
  new `BoardChange` subclass and a matching tool rather than special-casing
  inside `apply_node`.
- **Liskov Substitution Principle (L):** avoid deep inheritance hierarchies.
  Prefer Pydantic/SQLModel composition and discriminated unions over subclassing
  for behavior variation.
- **Interface Segregation Principle (I):** keep request/response models and
  function signatures focused. Do not force callers to provide fields they do
  not need.
- **Dependency Inversion Principle (D):** depend on abstractions where it makes
  testing or swapping implementations easier. In the backend, services are
  currently concrete functions, which is acceptable for this codebase size;
  introduce protocols or injectable interfaces only when a clear benefit
  outweighs the added indirection.

**Comments**

- Keep existing comments on refactor — they carry intent and provenance.
- Write WHY, not WHAT. Skip `// increment counter` above `i++`.
- Docstrings on public functions: intent plus one usage example.
- Reference issue numbers / commit SHAs when a line exists because of a specific
  bug or upstream constraint.

**Dependencies**

- Inject dependencies through constructor/parameter, not global/import.
- Wrap third-party libraries behind a thin interface owned by this project.

**Structure**

- Follow the framework's convention (FastAPI/SQLModel in the backend, Next.js
  App Router in the frontend).
- Prefer small focused modules over god files.
- Keep related code together and unrelated code apart. Match the existing
  feature-based directory layout.

**Formatting**

- Use the project's configured formatter and linter:
  - Backend: `ruff format`, `ruff check`, and `mypy` (via `uv run`).
  - Frontend: `prettier` and `eslint` (via `pnpm lint`).
- Do not discuss style beyond what the formatter enforces.

**Logging**

- Structured JSON when logging for debugging / observability.
- Plain text only for user-facing CLI output.

**Balance.** These principles are guidelines, not rules. A minimal, tested,
obvious change beats a "perfectly" abstracted one that touches ten files.

---

## 7. Design and UI conventions

Read before building or changing any UI:

- `DESIGN.md` — visual system: "The Andon Line", colors, typography, elevation,
  component rules, do's/don'ts.
- `PRODUCT.md` — product strategy, audience, positioning, anti-references,
  accessibility commitment.

Key rules:

- **Electric Violet** is the only action/agent accent (`--primary`).
- **Andon colors** (sky, amber, emerald) appear only as the 6px status dot in
  column headers.
- **Backlog** uses a neutral gray dot, not an andon color.
- Surfaces are **flat at rest**; shadows appear only on hover/drag/open.
- All transitions are ≤150 ms.
- Every number that can change is set in Geist Mono with `tabular-nums`.
- WCAG 2.1 AA is the target: sufficient contrast, visible focus, keyboard
  operable drag-and-drop, and `prefers-reduced-motion` alternatives.
- Both light and dark themes ship together.

---

## 8. Backend API and data model

### Tables

- `users` — accounts. OAuth users have `hashed_password = NULL` and store the
  provider identity in `oauth_provider` + `oauth_provider_id`.
- `tasks` — kanban cards.
- `projects` — optional time-tracking buckets.
- `work_blocks` — completed focus/manual work sessions on a task.

### Column IDs

Fixed literal values: `backlog`, `todo`, `in_progress`, `done`.

### Key endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness check |
| `GET /auth/oauth/{provider}` | Start OAuth sign-in (`google` or `github`) |
| `GET /auth/oauth/{provider}/callback` | Provider callback; redirects to frontend with JWT |
| `GET /tasks` | List tasks; `?include_archived=true` includes archived |
| `POST /tasks` | Create a task |
| `PATCH /tasks/{id}` | Full replace update (title, description, project_id, checklist, due_date) |
| `PATCH /tasks/{id}/move` | Move/reorder within or across columns |
| `PATCH /tasks/{id}/archive` | Archive or unarchive a task |
| `DELETE /tasks/{id}` | Delete a task (cascade-deletes its work blocks) |
| `GET/POST /projects` | List / create projects |
| `PATCH /projects/{id}` | Full replace update |
| `DELETE /projects/{id}` | Delete project; unlinks its tasks (`ON DELETE SET NULL`) |
| `POST /projects/daily-tasks/generate` | Generate today's daily task per enabled project |
| `GET/POST /tasks/{id}/work-blocks` | List / create work blocks |
| `GET /work-blocks/stats/daily` | Daily minutes aggregated by project |

### Position handling

`move`, `archive`, and `delete` all reindex the affected column(s) so
`position` values stay dense (no gaps).

### Full-replace PATCH gotcha

Because `PATCH /tasks/{id}` and `PATCH /projects/{id}` are full replaces, any
frontend code that updates a task must pass the current `checklist` and
`due_date`; any project update must pass the current `daily_template`. Omitting
them silently clears the field.

---

## 9. Frontend architecture

### Routes

- `/` — Dashboard: projects list + 7-day stacked bar chart of focus time.
- `/board` — Kanban board with drag-and-drop columns.

### State flow

1. Server Components fetch initial data from FastAPI.
2. Mutations go through Server Actions → FastAPI.
3. `revalidatePath` invalidates the relevant routes after mutations.
4. Zustand `board-store.ts` provides optimistic updates + rollback + toast on
   failure for drag, delete, archive, and checklist edits.

### Pomodoro timer

- State lives in `stores/pomodoro-store.ts` and persists to `localStorage`.
- Only finished work blocks linked to a task are sent to FastAPI as
  `work_blocks`; stopped/aborted sessions are never persisted.
- Timer state survives reloads, but a block only counts if it finishes while the
  page is open.

### Daily tasks

- `DailyTaskGenerator` (mounted in root layout) triggers once per
  browser-local day.
- It calls the `generateDailyTasks` Server Action → `POST /projects/daily-tasks/generate`.
- Idempotent per UTC day on the backend (`daily_last_generated`).
- Known placeholder trigger: will move to real login/session-start event once
  auth ships.

---

## 10. Security considerations

- **Auth is implemented.** FastAPI issues/verifies HS256 JWTs; Next.js stores
  them in an HttpOnly cookie. OAuth users (`google`, `github`) have no password.
- **FastAPI is the single writer to Postgres.** Next.js Server Actions proxy
  mutations; they do not touch the DB directly.
- **Input validation** is done via Pydantic/SQLModel on the backend; invalid
  payloads return `422`.
- **No secrets in the repo.** `.env` files are gitignored; OAuth client secrets
  and `JWT_SECRET_KEY` must be set in the environment.
- Backend `DATABASE_URL` can be overridden by environment.
- Do not expose backend endpoints to the browser directly except for the OAuth
  initiation/callback flow and the future agent streaming endpoint.

---

## 11. Common gotchas and rules

- **No migration tool.** If you change a SQLModel table, existing local DBs need
  a manual `ALTER TABLE` or `docker volume rm`.
- **Full-replace PATCH.** Always pass complete state; omitted fields are wiped.
- **Archived tasks** are excluded from `GET /tasks` by default.
- **Project color** is derived client-side from creation order; it is not stored.
- **Daily task title format:** `Daily - DD-MM-YY - <project>` with optional
  ` - <template.title>` suffix. Do not change without updating tests.
- **Avoid browser automation for verification.** Prefer `curl` against
  `:8000` and `docker exec ... psql` checks.
- **Do not use `react-beautiful-dnd`.** Use @dnd-kit.
- **LangGraph is used directly.** Avoid classic LangChain chains and
  `AgentExecutor` abstractions when the agent layer arrives.

---

## 12. Useful references

- `README.md` — user-facing features and running instructions
- `CLAUDE.md` — Claude Code specific guidance, agent architecture sketch,
  feature scope, pomodoro behavior
- `DESIGN.md` — visual design system
- `PRODUCT.md` — product context
- `TESTING.md` — manual test plan
- `HISTORY.md` — session log; append a dated entry at the end of each working
  session describing what landed, decisions made, and what's next

---

## 13. Git workflow

- **Never commit on the user's behalf.** The user always commits manually.
  Do not run `git commit`, `git push`, `git reset`, `git rebase`, or any other
  git mutation unless the user explicitly asks for it. It is fine to stage
  files or inspect git status/diff to help the user understand what changed.

---

## 14. Backlog / upcoming work

Larger items discussed and not yet started. Pick from here when deciding what
to work on next.

### Product-defining features

1. **Agent graph with HITL approval** - the core differentiator. LangGraph
   state machine with `agent → tools → propose → apply` nodes; `interrupt()`
   for diff approval; checkpointed per `thread_id` (= board_id). First tool to
   wire end to end: `create_task`.
2. **Paste-to-tickets** - syllabus/project brief → structured extraction
   (`TaskDraft` / `ExtractionResult`) → same propose → approve flow, reusing
   `create_task`.
3. **Semantic search over cards** - pgvector embeddings for `search_tasks`;
   the extension is installed but no embedding pipeline or table exists yet.
4. **Auth (JWT in FastAPI)** — *implemented.* FastAPI issues/verifies its own
   HS256 tokens; Next.js stores them in an `HttpOnly` cookie and proxies them
   as `Authorization: Bearer` tokens. Projects and tasks are owned by users.

### Observability and evals

5. **Langfuse tracing** on every agent run.
6. **pytest eval suite** asserting correct tool selection and arguments;
   publish results in `README.md`.

### Frontend test coverage

7. **@dnd-kit interaction tests** for drag-and-drop on `/board`.
8. **Page-level tests** for `/` (dashboard) and `/board`.
9. **Server Action unit tests** - currently mocked in components; test their
   error handling and `revalidatePath` calls directly.

### Roadmap items

10. **Standup digest** - background job summarizing recent work.
11. **Quiz-me study mode** over board content.
12. **MCP server** exposing the board to other agents.
13. **Duplicate-card detection** via embeddings.
14. **Local-day bucketing** for the weekly dashboard chart (currently buckets by
    UTC calendar day, so late-night non-UTC work can land on the wrong day).
15. **Refresh tokens and session revocation** — currently planned as a later
    enhancement after the initial JWT cookie auth is wired; add token rotation,
    a `/refresh` endpoint, and a revocation table when multi-user/session
    management becomes a priority.
16. **Agent chat persistence** — persist agent chat history and `thread_id`
    across page reloads. Options: `localStorage` for same-browser quick win, or
    a backend `threads`/`messages` table for cross-device persistence. Not yet
    started.
