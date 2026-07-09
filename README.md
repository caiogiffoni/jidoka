# Jidoka

A Trello-style kanban board you can drive by hand or through an LLM agent — with human-in-the-loop approval for every change the agent wants to make.

The name comes from the Toyota principle *jidoka*: automation with a human touch. The agent proposes; you approve, edit, or reject; only then does anything touch the board.


## What it does

- **A real kanban board** — create, edit, and drag cards across columns by hand, like any Trello board. The agent is a layer on top, not the only way in.
- **Chat with your board** — an agent with tools (`create_task`, `move_task`, `breakdown_task`, `prioritize_backlog`, `search_tasks`) that streams its actions to the UI as cards move live.
- **Human-in-the-loop approval** — the agent never writes directly. It builds a diff of proposed changes, execution pauses, and resumes only on your decision.
- **Paste-to-tickets** — paste a syllabus or project brief and get structured task extraction, routed through the same propose → approve flow.
- **Semantic search** over cards via pgvector embeddings.
- **Time tracking** — start a pomodoro-style work block from any card (or log minutes manually) to see how long each task actually took. Tasks link to projects, so time invested rolls up per project.
- **Traced and evaluated** — Langfuse tracing on every agent run, plus a pytest eval suite asserting correct tool selection and arguments. *(Results will be published here.)*

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind v4, shadcn/ui, dnd-kit |
| Agent | Python, FastAPI, LangGraph (checkpointed state machine, `interrupt()` for approval) |
| Data | Postgres + pgvector |
| Streaming | SSE from FastAPI, consumed via the Vercel AI SDK |
| Infra | Docker Compose |

The agent is an explicit LangGraph state machine because the feature's control flow *is* the graph: an agent ↔ tools loop, an interrupt for approval, and checkpointed state resumable per board.

## Roadmap

- Standup digest (background job)
- Quiz-me study mode over board content
- MCP server exposing the board to other agents
- Duplicate-card detection via embeddings
- Card attachments / vision, voice input, cost dashboard
