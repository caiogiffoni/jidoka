# QA-002 — Card lifecycle

Manual QA from an API consumer's perspective against `http://localhost:8000`.
Register first and export `TOKEN` (see qa_001_auth.md, steps 1–3).

```bash
AUTH="Authorization: Bearer $TOKEN"
JSON='Content-Type: application/json'
```

## Steps

1. Create three cards in `backlog`:

   ```bash
   for t in "card A" "card B" "card C"; do
     curl -s -X POST http://localhost:8000/tasks -H "$AUTH" -H "$JSON" \
       -d "{\"title\":\"$t\",\"column_id\":\"backlog\"}"
   done
   ```

   **Expected:** each returns HTTP 201 with `position` 0, 1, 2 respectively.
   Save each `id` (e.g. `A=...`, `B=...`, `C=...` via `jq -r .id`).

2. Full-replace edit of card A:

   ```bash
   curl -s -X PATCH http://localhost:8000/tasks/$A -H "$AUTH" -H "$JSON" \
     -d '{"title":"card A (edited)","description":"new description","project_id":null,"checklist":[{"text":"step 1","checked":true}],"due_date":"2030-01-15"}'
   ```

   **Expected:** HTTP 200; title/description/checklist/due_date updated.
   **Gotcha:** PATCH is a full replace — omitting `checklist` or `due_date`
   silently wipes them.

3. Move card A to `done`:

   ```bash
   curl -s -X PATCH http://localhost:8000/tasks/$A/move -H "$AUTH" -H "$JSON" \
     -d '{"column_id":"done","position":0}'
   ```

   **Expected:** HTTP 200, `column_id: "done"`, `position: 0`. Remaining
   backlog cards (B, C) are re-indexed to positions 0, 1 — verify with
   `curl -s http://localhost:8000/tasks -H "$AUTH" | jq`.

4. Archive card B:

   ```bash
   curl -s -X PATCH http://localhost:8000/tasks/$B/archive -H "$AUTH" -H "$JSON" \
     -d '{"archived":true}'
   curl -s http://localhost:8000/tasks -H "$AUTH" | jq 'map(.id)'
   ```

   **Expected:** HTTP 200 with `archived: true`. Card B is absent from the
   default list but present with
   `curl -s 'http://localhost:8000/tasks?include_archived=true' -H "$AUTH"`.

5. Unarchive card B:

   ```bash
   curl -s -X PATCH http://localhost:8000/tasks/$B/archive -H "$AUTH" -H "$JSON" \
     -d '{"archived":false}'
   ```

   **Expected:** HTTP 200, `archived: false`, re-appended at the **end** of
   `backlog` (position 1, after card C at 0).

6. Log a work block on card C, then delete card C:

   ```bash
   curl -s -X POST http://localhost:8000/tasks/$C/work-blocks -H "$AUTH" -H "$JSON" \
     -d '{"minutes":30}'
   curl -s -o /dev/null -w '%{http_code}\n' -X DELETE http://localhost:8000/tasks/$C -H "$AUTH"
   ```

   **Expected:** work block 201; delete 204. Card C gone from the list, its
   work blocks cascade-deleted:
   `docker exec jidoka-db-1 psql -U jidoka -d jidoka -c "select count(*) from work_blocks;"`.

## Unhappy paths to verify

- `POST /tasks` with `"column_id":"bogus"` → 422.
- `POST /tasks` with no `title` → 422.
- `PATCH .../move` with `"position":-1` → 422.
- Any operation on a random UUID (`PATCH`, `move`, `archive`, `DELETE`,
  work-block list/create) → 404.
- All of the above without `Authorization` header → 401 or 403.
- A second registered user gets 404 (not 403) when touching the first user's
  card IDs, and sees an empty `GET /tasks`.
