"""Hypothesis property-based tests for the Jidoka board API.

Properties asserted (from the spec):
- Positions stay dense (exactly 0..n-1 per column) after any sequence of
  create/move/archive/unarchive/delete operations.
- Timed work blocks store minutes == max(1, round(delta_seconds / 60)).
- PATCH /tasks/{id} is a full replace: carried state round-trips unchanged.
- GET /work-blocks/stats/daily reports, per (UTC day, project), the exact
  sum of that project's block minutes.

Note on isolation: hypothesis runs many examples inside a single pytest
fixture scope, so each example only asserts over the rows it created itself
(by id), never over global table state.
"""

from datetime import date, datetime, time, timedelta, timezone

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings

# The `client` fixture is function-scoped and shared across examples by
# design: every example asserts only over the rows it created (by id),
# so leftover state from earlier examples cannot falsify a property.
_SHARED_FIXTURE = [HealthCheck.function_scoped_fixture]

COLUMN_IDS = ["backlog", "todo", "in_progress", "done"]

# Text safe for JSON + Postgres (no surrogates, no control chars/NUL).
_text = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")))
# Non-blank text with no leading/trailing whitespace, so the backend's
# strip-and-drop-blank checklist cleaning leaves it unchanged.
_stripped_text = _text.filter(lambda s: s != "" and s.strip() == s)


# ---------------------------------------------------------------------------
# 1. Positions stay dense under random operation sequences
# ---------------------------------------------------------------------------

_op_strategy = st.tuples(
    st.sampled_from(["create", "move", "archive", "unarchive", "delete"]),
    st.sampled_from(COLUMN_IDS),  # column for create/move
    st.integers(min_value=0, max_value=30),  # position for move
    st.integers(min_value=0, max_value=1_000_000),  # task selector
)


def _replay_ops(client, ops):
    """Replay operations via the API, tracking live/archived task ids."""
    live: list[str] = []
    archived: set[str] = set()
    for kind, column, position, selector in ops:
        active = [t for t in live if t not in archived]
        if kind == "create" or not live:
            r = client.post("/tasks", json={"title": "pbt", "column_id": column})
            assert r.status_code == 201, r.text
            live.append(r.json()["id"])
        elif kind == "move" and active:
            task_id = active[selector % len(active)]
            r = client.patch(
                f"/tasks/{task_id}/move",
                json={"column_id": column, "position": position},
            )
            assert r.status_code == 200, r.text
        elif kind == "archive" and active:
            task_id = active[selector % len(active)]
            r = client.patch(f"/tasks/{task_id}/archive", json={"archived": True})
            assert r.status_code == 200, r.text
            archived.add(task_id)
        elif kind == "unarchive" and archived:
            pool = sorted(archived)
            task_id = pool[selector % len(pool)]
            r = client.patch(f"/tasks/{task_id}/archive", json={"archived": False})
            assert r.status_code == 200, r.text
            archived.discard(task_id)
        elif kind == "delete":
            task_id = live[selector % len(live)]
            r = client.delete(f"/tasks/{task_id}")
            assert r.status_code == 204, r.text
            live.remove(task_id)
            archived.discard(task_id)
    return live


@given(ops=st.lists(_op_strategy, min_size=10, max_size=25))
@settings(max_examples=10, deadline=None, suppress_health_check=_SHARED_FIXTURE)
def test_positions_stay_dense_under_random_operation_sequences(client, ops):
    _replay_ops(client, ops)

    # Density is a global invariant (every create/move/archive/delete reindexes
    # whole columns), so assert over ALL of the user's unarchived tasks - not
    # just this example's - since examples share one fixture transaction.
    tasks = client.get("/tasks", params={"include_archived": "true"}).json()
    by_column: dict[str, list[int]] = {c: [] for c in COLUMN_IDS}
    for task in tasks:
        if not task["archived"]:
            by_column[task["column_id"]].append(task["position"])

    for column in COLUMN_IDS:
        positions = sorted(by_column[column])
        assert positions == list(range(len(positions))), (
            f"column {column!r} has positions {positions}, "
            f"expected {list(range(len(positions)))}"
        )


# ---------------------------------------------------------------------------
# 2. Timed work block minutes match the duration
# ---------------------------------------------------------------------------


@given(
    started=st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
        timezones=st.just(timezone.utc),
    ),
    duration_seconds=st.integers(min_value=0, max_value=30 * 24 * 3600),
)
@settings(max_examples=20, deadline=None, suppress_health_check=_SHARED_FIXTURE)
def test_timed_work_block_minutes_match_duration(client, started, duration_seconds):
    ended = started + timedelta(seconds=duration_seconds)
    task = client.post("/tasks", json={"title": "pbt"}).json()

    r = client.post(
        f"/tasks/{task['id']}/work-blocks",
        json={
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    expected = max(1, round(duration_seconds / 60))
    assert r.json()["minutes"] == expected
    assert r.json()["minutes"] >= 1


# ---------------------------------------------------------------------------
# 3. Full-replace PATCH round-trips task state
# ---------------------------------------------------------------------------


@given(
    title=_stripped_text,
    description=st.one_of(st.none(), _text),
    checklist=st.lists(st.tuples(_stripped_text, st.booleans()), max_size=5),
    due_date=st.one_of(
        st.none(), st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31))
    ),
    with_project=st.booleans(),
)
@settings(max_examples=20, deadline=None, suppress_health_check=_SHARED_FIXTURE)
def test_full_replace_patch_round_trips_task_state(
    client, title, description, checklist, due_date, with_project
):
    project_id = None
    if with_project:
        r = client.post("/projects", json={"name": "pbt project"})
        assert r.status_code == 201, r.text
        project_id = r.json()["id"]

    task = client.post("/tasks", json={"title": "initial"}).json()

    payload = {
        "title": title,
        "description": description,
        "project_id": project_id,
        "checklist": [{"text": text, "checked": checked} for text, checked in checklist],
        "due_date": due_date.isoformat() if due_date is not None else None,
    }
    r = client.patch(f"/tasks/{task['id']}", json=payload)
    assert r.status_code == 200, r.text

    fetched = next(
        t for t in client.get("/tasks").json() if t["id"] == task["id"]
    )
    assert fetched["title"] == title
    assert fetched["description"] == description
    assert fetched["project_id"] == project_id
    assert fetched["checklist"] == payload["checklist"]
    assert fetched["due_date"] == payload["due_date"]


# ---------------------------------------------------------------------------
# 4. Daily stats minutes equal the exact sum of blocks
# ---------------------------------------------------------------------------


@given(data=st.data())
@settings(max_examples=15, deadline=None, suppress_health_check=_SHARED_FIXTURE)
def test_daily_stats_minutes_equal_sum_of_blocks(client, data):
    today = datetime.now(timezone.utc).date()
    midnight = datetime.combine(today, time.min, tzinfo=timezone.utc)

    n_projects = data.draw(st.integers(min_value=1, max_value=3))
    project_ids = []
    for i in range(n_projects):
        r = client.post("/projects", json={"name": f"pbt-stats-{i}"})
        assert r.status_code == 201, r.text
        project_ids.append(r.json()["id"])

    expected: dict[str, int] = {}
    n_blocks = data.draw(st.integers(min_value=1, max_value=8))
    for _ in range(n_blocks):
        project_id = project_ids[data.draw(st.integers(min_value=0, max_value=n_projects - 1))]
        task = client.post(
            "/tasks", json={"title": "pbt", "project_id": project_id}
        ).json()

        kind = data.draw(st.sampled_from(["manual", "timed"]))
        if kind == "manual":
            minutes = data.draw(st.integers(min_value=1, max_value=600))
            body = {"minutes": minutes}
            expected_minutes = minutes
        else:
            start_minute = data.draw(st.integers(min_value=0, max_value=23 * 60))
            duration_seconds = data.draw(st.integers(min_value=0, max_value=3600))
            started = midnight + timedelta(minutes=start_minute)
            ended = started + timedelta(seconds=duration_seconds)
            body = {
                "started_at": started.isoformat(),
                "ended_at": ended.isoformat(),
            }
            expected_minutes = max(1, round(duration_seconds / 60))

        r = client.post(f"/tasks/{task['id']}/work-blocks", json=body)
        assert r.status_code == 201, r.text
        assert r.json()["minutes"] == expected_minutes
        expected[project_id] = expected.get(project_id, 0) + expected_minutes

    rows = client.get("/work-blocks/stats/daily", params={"days": 7}).json()
    today_rows = {
        row["project_id"]: row["minutes"]
        for row in rows
        if row["date"] == today.isoformat() and row["project_id"] in expected
    }
    assert today_rows == {pid: float(minutes) for pid, minutes in expected.items()}
