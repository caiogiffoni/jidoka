# QA-004 — Daily task generation

Manual QA from an API consumer's perspective against `http://localhost:8000`.
Register first and export `TOKEN` (see qa_001_auth.md).

```bash
AUTH="Authorization: Bearer $TOKEN"
JSON='Content-Type: application/json'
```

## Steps

1. Create a daily-enabled project with a template:

   ```bash
   curl -s -X POST http://localhost:8000/projects -H "$AUTH" -H "$JSON" \
     -d '{"name":"Spanish","daily_enabled":true,"daily_template":{"title":"Anki review","description":"Clear the review queue","checklist":["due cards","new cards"]}}'
   ```

   **Expected:** HTTP 201; the project echoes `daily_enabled: true` and the
   template.

2. Trigger generation:

   ```bash
   curl -s -X POST http://localhost:8000/projects/daily-tasks/generate -H "$AUTH" | jq
   ```

   **Expected:** HTTP 201 with exactly one task:
   - `title` = `Daily - DD-MM-YY - Spanish - Anki review` (today's **UTC**
     date, `%d-%m-%y`)
   - `column_id` = `"todo"`, appended at the end of the column
   - `description` = `"Clear the review queue"`
   - `checklist` = both items with `checked: false`
   - `project_id` = the project from step 1

3. Trigger generation again the same UTC day:

   ```bash
   curl -s -X POST http://localhost:8000/projects/daily-tasks/generate -H "$AUTH"
   ```

   **Expected:** HTTP 201 with `[]` — idempotent per UTC day, no duplicate card.

4. Confirm idempotency marker in the DB:

   ```bash
   docker exec jidoka-db-1 psql -U jidoka -d jidoka \
     -c "select name, daily_last_generated from projects;"
   ```

   **Expected:** `daily_last_generated` = today's date (`YYYY-MM-DD`).

5. Template without a title: create another daily project with
   `"daily_template":{"checklist":["x"]}` (no `title`), generate on a fresh
   UTC day (or clear `daily_last_generated` in psql), and verify the card is
   titled `Daily - DD-MM-YY - <project>` with no trailing suffix.

## Unhappy paths to verify

- Project with `daily_enabled: false` produces nothing (generate returns `[]`
  when it is the only due candidate).
- Daily-enabled project with `daily_template: null` is skipped (no crash, no
  card).
- `POST /projects` with `daily_enabled: true` and no template → 422.
- `POST /projects/daily-tasks/generate` without a token → 401 or 403.
- A second user's generate call creates cards only from their own projects.
- **Full-replace gotcha:** `PATCH /projects/$P` that omits `daily_template`
  sets it to null, and the project silently stops generating cards — verify
  with `GET /projects` and a generate call.
