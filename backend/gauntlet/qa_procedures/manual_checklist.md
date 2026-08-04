# Manual QA checklist — Jidoka backend

Human checklist for a full pass over auth, card lifecycle, projects/time
rollup, and daily tasks. Backend + Postgres up via `docker compose up -d`.
Detailed curl walkthroughs live in `qa_001`–`qa_004`; this is the condensed
pass/fail sheet. Export `TOKEN` (register + login) before board checks.

```bash
AUTH="Authorization: Bearer $TOKEN"
PSQL="docker exec jidoka-db-1 psql -U jidoka -d jidoka -c"
```

## Happy path

- [ ] Register → 201 with `user` + `token`; no password hash in the response.
- [ ] `GET /auth/me` with Bearer token → 200, correct identity.
- [ ] Login → 200 with fresh token; `me` still works with it.
- [ ] Create 3 tasks in one column → positions 0, 1, 2.
- [ ] Full-replace `PATCH /tasks/{id}` updates title/description/checklist/due_date.
- [ ] Move a card across columns → lands at requested position; source column re-indexed densely.
- [ ] Archive → hidden from default `GET /tasks`; visible with `?include_archived=true`.
- [ ] Unarchive → re-appended at the end of its column.
- [ ] Timed work block → server computes `minutes` from timestamps.
- [ ] Manual work block (`{"minutes":N}`) → 201.
- [ ] `GET /work-blocks/stats/daily` shows summed minutes per (UTC day, project).
- [ ] Delete project → 204; its tasks survive with `project_id: null`; minutes move to the null-project bucket.
- [ ] Daily-enabled project → generate → one card in `todo` titled `Daily - DD-MM-YY - <project>[ - <template>]` with template description/checklist.
- [ ] Delete task → 204; its work blocks cascade-deleted.
- [ ] Agent HITL create_task → message → interrupt → approve → task appears in target column.

## Error paths

- [ ] Login with wrong password / unknown email → 401 (identical shape).
- [ ] Duplicate email / username on register → 409.
- [ ] Every board endpoint without a token → 401 or 403.
- [ ] Invalid Bearer token → 401.
- [ ] Operations on random UUIDs (task/project PATCH, move, archive, DELETE, work-blocks) → 404.
- [ ] Second user touching first user's IDs → 404; their `GET /tasks` / stats are empty of the first user's data.

## Edge cases

- [ ] `POST /tasks` with bogus `column_id` → 422.
- [ ] `POST /tasks` without `title` → 422.
- [ ] `move` with negative `position` → 422.
- [ ] Work block with neither timestamps nor minutes → 422; `minutes: 0` → 422; `ended_at < started_at` → 422.
- [ ] `daily_enabled: true` without `daily_template` → 422.
- [ ] Second generate call same UTC day → 201 with `[]` (no duplicate card).
- [ ] Agent rejects a diff → no task created.
- [ ] Agent stream without auth → 401.
- [ ] Agent receives invalid tool args (blank title / bad column) → error event, no DB write.
- [ ] Archiving the middle card of three → remaining positions re-packed to 0, 1.
- [ ] **Full-replace PATCH gotcha:** `PATCH /tasks/{id}` omitting `checklist`/`due_date` wipes them; `PATCH /projects/{id}` omitting `daily_template` wipes it (project silently stops generating dailies). Verify before/after via `GET`.

## State verification

- [ ] Positions dense per column:
  `$PSQL "select column_id, position, title from tasks where not archived order by column_id, position;"`
- [ ] Cascade delete: after deleting a task with work blocks,
  `$PSQL "select count(*) from work_blocks;"` drops accordingly.
- [ ] Project delete unlinks, never deletes tasks:
  `$PSQL "select id, title, project_id from tasks;"` — `project_id` null, row present.
- [ ] Daily idempotency marker: `$PSQL "select name, daily_last_generated from projects;"` = today's UTC date after generate.
- [ ] No plaintext passwords: `$PSQL "select username, left(hashed_password,7) from users;"` — bcrypt hashes only.
- [ ] Backend logs (`docker compose logs backend --tail=50`) show no tracebacks or 500s during the whole pass.
- [ ] No side effects across users: row counts in `tasks`/`projects`/`work_blocks` match what each user's API views report.
