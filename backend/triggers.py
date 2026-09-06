"""Endpoint trigger support for task creation.

A task (or daily template) may carry optional ``trigger_urls``. When the
task is created, the backend GETs each URL once, in order, expects a
plain-text body from each, and appends the stripped bodies as final
checklist items. The motivating use case is a Lambda that picks a random
LeetCode problem, so the generated card arrives with e.g. "347. Top K
Frequent Elements" already on its checklist.

Trigger failures (timeout, non-2xx, network error) are logged and swallowed
by design: a flaky endpoint must never block task creation.
"""

import logging
from collections.abc import Callable

import httpx

from models import ChecklistItem

logger = logging.getLogger(__name__)

TRIGGER_TIMEOUT_SECONDS = 5.0

FetchFn = Callable[[str], tuple[int, str]]


def http_get(url: str) -> tuple[int, str]:
    """GET ``url`` and return (status_code, text body)."""
    response = httpx.get(url, timeout=TRIGGER_TIMEOUT_SECONDS)
    return response.status_code, response.text


def fetch_trigger_item(url: str, *, fetcher: FetchFn | None = None) -> str | None:
    """Fetch the checklist item text from a trigger endpoint.

    Returns the stripped body on any 2xx status; returns None (never raises)
    on non-2xx status or any request failure, logging a warning either way.
    """
    fetch = fetcher or http_get
    try:
        status, body = fetch(url)
    except Exception as exc:
        logger.warning("trigger endpoint failed url=%s error=%s", url, type(exc).__name__)
        return None
    if not 200 <= status < 300:
        logger.warning("trigger endpoint non-2xx url=%s status=%s", url, status)
        return None
    return body.strip() or None


def append_trigger_item(
    checklist: list[dict], url: str, *, fetcher: FetchFn | None = None
) -> None:
    """Append the trigger endpoint's response to ``checklist`` in place.

    ``checklist`` is the raw JSON-bound representation (plain dicts), matching
    what both the Task JSON column and the daily generation loop build.
    """
    item = fetch_trigger_item(url, fetcher=fetcher)
    if item:
        checklist.append(ChecklistItem(text=item, checked=False).model_dump())
