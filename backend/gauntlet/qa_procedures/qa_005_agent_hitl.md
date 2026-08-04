# QA-005 — Agent HITL create_task flow

Manual QA from an API consumer's perspective against `http://localhost:8000`.
Backend and Postgres must be running (`docker compose up -d`).

## Setup

Register and export a token (see qa_001_auth.md), then define helpers:

```bash
AUTH="Authorization: Bearer $TOKEN"
JSON='Content-Type: application/json'
THREAD=$(uuidgen)
```

## Steps

1. Send a message to the agent:

   ```bash
   curl -s -N -X POST http://localhost:8000/agent/stream \
     -H "$AUTH" -H "$JSON" \
     -d "{\"thread_id\":\"$THREAD\",\"message\":\"Add a task to wire the HITL flow\"}" | tee /tmp/agent_interrupt.txt
   ```

   **Expected:** HTTP 200 with `Content-Type: text/event-stream`. The stream
   contains at least:
   - `event: message` (optional, agent acknowledgment)
   - `event: tool_call` with `name: create_task`
   - `event: interrupt` with `data.changes[0]` containing the proposed task
     (`title`, `column_id`, `description`, `project_id`, `checklist`)
   - `event: done`

2. Parse the interrupt payload and confirm the shape:

   ```bash
   grep -A1 '^data:' /tmp/agent_interrupt.txt | tail -n +2 | tr -d '\n' | jq '.changes[0]'
   ```

   **Expected:** A single `create_task` change with a non-empty title and a
   valid `column_id` (`backlog`, `todo`, `in_progress`, or `done`).

3. Approve the proposed diff:

   ```bash
   curl -s -N -X POST http://localhost:8000/agent/stream \
     -H "$AUTH" -H "$JSON" \
     -d "{\"thread_id\":\"$THREAD\",\"resume\":{\"approved\":true}}" | tee /tmp/agent_apply.txt
   ```

   **Expected:** HTTP 200 stream with `event: apply` containing
   `data.created_tasks[0]` matching the proposed task, followed by `event: done`.

4. Verify the task was persisted:

   ```bash
   curl -s http://localhost:8000/tasks -H "$AUTH" | jq '.[] | select(.title | contains("wire the HITL flow"))'
   ```

   **Expected:** Exactly one matching task with the proposed `column_id` and
   `user_id` equal to the current user.

## Unhappy paths to verify

- **Reject the diff:** send `resume: {"approved": false}` and confirm `GET
  /tasks` does not contain the proposed title.
- **Unauthenticated:** omit `Authorization` header → 401 or 403.
- **Invalid tool args:** patch or simulate an LLM that returns `create_task`
  with `"title": ""` or `"column_id": "bogus"`; expect an `event: error`
  and no persisted task.
- **Cross-user project_id:** approve a diff whose `project_id` belongs to a
  different user; expect the apply node to reject it (error event, no task
  created under the wrong project).
- **Resuming a fresh thread:** send `resume` on a `thread_id` that has no
  pending interrupt; expect an error event or 4xx response.
