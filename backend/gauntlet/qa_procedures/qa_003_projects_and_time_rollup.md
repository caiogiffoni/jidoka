# QA-003 — Projects and time rollup

Manual QA from an API consumer's perspective against `http://localhost:8000`.
Register first and export `TOKEN` (see qa_001_auth.md).

```bash
AUTH="Authorization: Bearer $TOKEN"
JSON='Content-Type: application/json'
```

## Steps

1. Create a project:

   ```bash
   curl -s -X POST http://localhost:8000/projects -H "$AUTH" -H "$JSON" \
     -d '{"name":"Deep Work"}' | tee /tmp/proj.json
   P=$(jq -r .id /tmp/proj.json)
   ```

   **Expected:** HTTP 201 with `id`, `name`, `daily_enabled: false`.

2. Create a task linked to the project:

   ```bash
   curl -s -X POST http://localhost:8000/tasks -H "$AUTH" -H "$JSON" \
     -d "{\"title\":\"focus session\",\"project_id\":\"$P\"}" | tee /tmp/task.json
   T=$(jq -r .id /tmp/task.json)
   ```

   **Expected:** HTTP 201, `project_id` echoes the project id.

3. Log a timed work block (25 minutes, derived from timestamps):

   ```bash
   START=$(date -u -d '25 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
   END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
   curl -s -X POST http://localhost:8000/tasks/$T/work-blocks -H "$AUTH" -H "$JSON" \
     -d "{\"started_at\":\"$START\",\"ended_at\":\"$END\"}"
   ```

   **Expected:** HTTP 201 with `minutes: 25` computed server-side.

4. Log a manual work block (minutes only):

   ```bash
   curl -s -X POST http://localhost:8000/tasks/$T/work-blocks -H "$AUTH" -H "$JSON" \
     -d '{"minutes":40}'
   ```

   **Expected:** HTTP 201, `minutes: 40`, null timestamps.

5. Check the daily rollup:

   ```bash
   curl -s http://localhost:8000/work-blocks/stats/daily -H "$AUTH" | jq
   ```

   **Expected:** a row for today's UTC date with `project_id` = `$P`,
   `project_name: "Deep Work"`, `minutes: 65`.

6. Delete the project:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:8000/projects/$P -H "$AUTH"
   curl -s http://localhost:8000/tasks -H "$AUTH" | jq ".[] | select(.id==\"$T\")"
   ```

   **Expected:** HTTP 204. The task survives with `project_id: null`.

7. Re-check the rollup:

   ```bash
   curl -s http://localhost:8000/work-blocks/stats/daily -H "$AUTH" | jq
   ```

   **Expected:** the 65 minutes are still counted, now in a row with
   `project_id: null` and `project_name: null`.

## Unhappy paths to verify

- `POST /projects` with `{"daily_enabled":true}` and no `daily_template` → 422.
- Creating a task with a random `project_id` → 404.
- `PATCH /projects/{random-uuid}` and `DELETE /projects/{random-uuid}` → 404.
- Work block with neither timestamps nor `minutes` (`{}`) → 422.
- Work block with `"minutes":0` → 422.
- Work block with `ended_at` before `started_at` → 422.
- **Full-replace gotcha:** `PATCH /projects/$P` without `daily_template` wipes
  an existing template — verify with `GET /projects` before/after.
- A second user's stats never include the first user's minutes.
