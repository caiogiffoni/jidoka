"""Endpoint triggers on task creation and daily generation.

Each trigger URL is fired (GET) once per created task and the plain-text
response is appended as a final checklist item, in URL order. All HTTP is
faked here (named fakes, per AGENTS.md) - no test touches the network.
"""

import httpx

import triggers


class FakeHttpGet:
    """Injectable stand-in for triggers.http_get.

    Returns the canned (status, body) tuple for the requested URL, the
    fallback ``result`` when the URL has no canned entry, or raises the
    canned exception when set. Records every URL it was asked to fetch so
    tests can assert call order and counts.
    """

    def __init__(
        self,
        results: dict[str, tuple[int, str]] | None = None,
        result: tuple[int, str] | None = None,
        exc: Exception | None = None,
    ):
        self.calls: list[str] = []
        self.results = results or {}
        self.result = result
        self.exc = exc

    def __call__(self, url: str) -> tuple[int, str]:
        self.calls.append(url)
        if self.exc is not None:
            raise self.exc
        if url in self.results:
            return self.results[url]
        assert self.result is not None, "FakeHttpGet configured without result or exc"
        return self.result


def test_fetch_trigger_item_returns_stripped_body_on_2xx():
    fake = FakeHttpGet(result=(200, "  347. Top K Frequent Elements  "))
    assert triggers.fetch_trigger_item("https://lambda.example/pick", fetcher=fake) == (
        "347. Top K Frequent Elements"
    )
    assert fake.calls == ["https://lambda.example/pick"]


def test_fetch_trigger_item_returns_none_on_non_2xx():
    fake = FakeHttpGet(result=(500, "boom"))
    assert triggers.fetch_trigger_item("https://lambda.example/pick", fetcher=fake) is None


def test_fetch_trigger_item_returns_none_on_request_failure():
    fake = FakeHttpGet(exc=httpx.ConnectError("refused"))
    assert triggers.fetch_trigger_item("https://lambda.example/pick", fetcher=fake) is None


def test_fetch_trigger_item_returns_none_on_empty_body():
    fake = FakeHttpGet(result=(200, "   "))
    assert triggers.fetch_trigger_item("https://lambda.example/pick", fetcher=fake) is None


def test_append_trigger_item_appends_unchecked_checklist_item():
    checklist = [{"text": "Warm up", "checked": True}]
    fake = FakeHttpGet(result=(200, "Two Sum"))
    triggers.append_trigger_item(checklist, "https://lambda.example/pick", fetcher=fake)
    assert checklist == [
        {"text": "Warm up", "checked": True},
        {"text": "Two Sum", "checked": False},
    ]


def test_append_trigger_item_leaves_checklist_alone_on_failure():
    checklist = [{"text": "Warm up", "checked": False}]
    fake = FakeHttpGet(result=(503, "down"))
    triggers.append_trigger_item(checklist, "https://lambda.example/pick", fetcher=fake)
    assert checklist == [{"text": "Warm up", "checked": False}]


def test_create_task_fires_triggers_and_appends_responses_as_checklist_items(
    client, monkeypatch
):
    fake = FakeHttpGet(
        results={
            "https://lambda.example/leetcode": (200, " 347. Top K Frequent Elements "),
            "https://lambda.example/article": (200, "Read: Raft paper"),
        }
    )
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post(
        "/tasks",
        json={
            "title": "Daily practice",
            "trigger_urls": [
                "https://lambda.example/leetcode",
                "https://lambda.example/article",
            ],
            "checklist": [{"text": "Review yesterday's solution", "checked": False}],
        },
    )

    assert response.status_code == 201
    body = response.json()
    # Items land after the drafted checklist, in trigger_urls order.
    assert body["checklist"] == [
        {"text": "Review yesterday's solution", "checked": False},
        {"text": "347. Top K Frequent Elements", "checked": False},
        {"text": "Read: Raft paper", "checked": False},
    ]
    assert fake.calls == [
        "https://lambda.example/leetcode",
        "https://lambda.example/article",
    ]


def test_create_task_without_trigger_urls_never_fetches(client, monkeypatch):
    fake = FakeHttpGet(result=(200, "should not be used"))
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post("/tasks", json={"title": "Plain task"})

    assert response.status_code == 201
    assert response.json()["checklist"] == []
    assert fake.calls == []


def test_create_task_drops_blank_trigger_url_entries(client, monkeypatch):
    fake = FakeHttpGet(result=(200, "Two Sum"))
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post(
        "/tasks",
        json={
            "title": "Practice",
            "trigger_urls": ["", "https://lambda.example/pick", "   "],
        },
    )

    assert response.status_code == 201
    assert response.json()["checklist"] == [
        {"text": "Two Sum", "checked": False}
    ]
    assert fake.calls == ["https://lambda.example/pick"]


def test_create_task_trigger_failure_still_creates_task(client, monkeypatch):
    fake = FakeHttpGet(exc=httpx.TimeoutException("timed out"))
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post(
        "/tasks",
        json={
            "title": "Daily practice",
            "trigger_urls": ["https://lambda.example/pick"],
        },
    )

    assert response.status_code == 201
    assert response.json()["checklist"] == []
    assert fake.calls == ["https://lambda.example/pick"]


def test_create_task_trigger_non_2xx_still_creates_task(client, monkeypatch):
    fake = FakeHttpGet(result=(500, "boom"))
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post(
        "/tasks",
        json={
            "title": "Daily practice",
            "trigger_urls": ["https://lambda.example/pick"],
        },
    )

    assert response.status_code == 201
    assert response.json()["checklist"] == []


def test_create_task_rejects_invalid_trigger_url(client):
    response = client.post(
        "/tasks",
        json={"title": "Bad url", "trigger_urls": ["not a url"]},
    )
    assert response.status_code == 422


def test_generate_daily_tasks_appends_trigger_responses_to_checklist(
    client, monkeypatch
):
    fake = FakeHttpGet(
        results={
            "https://lambda.example/leetcode": (200, "226. Invert Binary Tree"),
            "https://lambda.example/kata": (200, "Bank OCR kata"),
        }
    )
    monkeypatch.setattr(triggers, "http_get", fake)
    client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Review spaced repetition"],
                "trigger_urls": [
                    "https://lambda.example/leetcode",
                    "https://lambda.example/kata",
                ],
            },
        },
    )

    response = client.post("/projects/daily-tasks/generate")

    assert response.status_code == 201
    assert response.json()[0]["checklist"] == [
        {"text": "Review spaced repetition", "checked": False},
        {"text": "226. Invert Binary Tree", "checked": False},
        {"text": "Bank OCR kata", "checked": False},
    ]
    assert fake.calls == [
        "https://lambda.example/leetcode",
        "https://lambda.example/kata",
    ]


def test_generate_daily_tasks_trigger_failure_still_generates(client, monkeypatch):
    fake = FakeHttpGet(exc=httpx.ConnectError("refused"))
    monkeypatch.setattr(triggers, "http_get", fake)
    client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Review spaced repetition"],
                "trigger_urls": ["https://lambda.example/pick"],
            },
        },
    )

    response = client.post("/projects/daily-tasks/generate")

    assert response.status_code == 201
    assert response.json()[0]["checklist"] == [
        {"text": "Review spaced repetition", "checked": False}
    ]


def test_daily_template_round_trips_trigger_urls(client):
    response = client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Solve"],
                "trigger_urls": [
                    "https://lambda.example/leetcode",
                    "https://lambda.example/kata",
                ],
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["daily_template"] == {
        "title": None,
        "description": None,
        "checklist": ["Solve"],
        "trigger_urls": [
            "https://lambda.example/leetcode",
            "https://lambda.example/kata",
        ],
    }


def test_daily_template_omits_trigger_urls_when_unset(client):
    response = client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Solve"]},
        },
    )
    assert response.status_code == 201
    assert "trigger_urls" not in response.json()["daily_template"]


def test_create_task_failed_trigger_does_not_block_later_endpoints(
    client, monkeypatch
):
    """A failing endpoint contributes no item but later URLs still fire."""
    fake = FakeHttpGet(
        results={
            "https://lambda.example/down": (500, "boom"),
            "https://lambda.example/up": (200, "Two Sum"),
        }
    )
    monkeypatch.setattr(triggers, "http_get", fake)

    response = client.post(
        "/tasks",
        json={
            "title": "Practice",
            "trigger_urls": [
                "https://lambda.example/down",
                "https://lambda.example/up",
            ],
        },
    )

    assert response.status_code == 201
    assert response.json()["checklist"] == [{"text": "Two Sum", "checked": False}]
    assert fake.calls == [
        "https://lambda.example/down",
        "https://lambda.example/up",
    ]


def test_update_task_never_refires_triggers(client, monkeypatch):
    """PATCH /tasks is a full replace of stored fields, not a re-creation -
    trigger_urls fire exactly once, at creation."""
    fake = FakeHttpGet(result=(200, "Two Sum"))
    monkeypatch.setattr(triggers, "http_get", fake)
    created = client.post(
        "/tasks",
        json={
            "title": "Practice",
            "trigger_urls": ["https://lambda.example/pick"],
        },
    ).json()
    assert created["checklist"] == [{"text": "Two Sum", "checked": False}]
    assert len(fake.calls) == 1

    response = client.patch(
        f"/tasks/{created['id']}",
        json={
            "title": "Practice (edited)",
            "checklist": created["checklist"],
        },
    )

    assert response.status_code == 200
    assert response.json()["checklist"] == created["checklist"]
    assert len(fake.calls) == 1


def test_update_project_replaces_trigger_urls(client):
    """PATCH /projects is a full replace of daily_template - a later update
    without trigger_urls clears them, one with them overwrites the list."""
    project = client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Solve"],
                "trigger_urls": ["https://lambda.example/leetcode"],
            },
        },
    ).json()

    response = client.patch(
        f"/projects/{project['id']}",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Solve"],
                "trigger_urls": [
                    "https://lambda.example/kata",
                    "https://lambda.example/article",
                ],
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["daily_template"]["trigger_urls"] == [
        "https://lambda.example/kata",
        "https://lambda.example/article",
    ]

    cleared = client.patch(
        f"/projects/{project['id']}",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {"checklist": ["Solve"]},
        },
    )
    assert cleared.status_code == 200
    assert "trigger_urls" not in cleared.json()["daily_template"]


def test_generate_daily_tasks_ignores_blank_trigger_url_entries(
    client, monkeypatch
):
    """Blank rows left in the template's list editor are dropped before URL
    validation and never fetched."""
    fake = FakeHttpGet(result=(200, "Two Sum"))
    monkeypatch.setattr(triggers, "http_get", fake)
    client.post(
        "/projects",
        json={
            "name": "Algorithms",
            "daily_enabled": True,
            "daily_template": {
                "checklist": ["Solve"],
                "trigger_urls": ["", "https://lambda.example/pick", "   "],
            },
        },
    )

    response = client.post("/projects/daily-tasks/generate")

    assert response.status_code == 201
    assert response.json()[0]["checklist"] == [
        {"text": "Solve", "checked": False},
        {"text": "Two Sum", "checked": False},
    ]
    assert fake.calls == ["https://lambda.example/pick"]
