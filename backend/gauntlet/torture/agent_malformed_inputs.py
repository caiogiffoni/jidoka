"""Send malformed POST /agent/stream payloads and assert graceful failure."""

import json
import sys
import uuid

import httpx

BASE = "http://localhost:8000"


def register_and_login() -> str:
    email = f"torture-{uuid.uuid4().hex[:8]}@example.com"
    username = f"torture{uuid.uuid4().hex[:8]}"
    password = "Password1!"

    r = httpx.post(
        f"{BASE}/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    if r.status_code == 201 and r.json().get("token"):
        return r.json()["token"]

    r = httpx.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": password},
    )
    r.raise_for_status()
    return r.json()["token"]


def has_error_event(text: str) -> bool:
    return 'event: error' in text


def check(label: str, response: httpx.Response, allowed: set[int]) -> bool:
    ok = response.status_code in allowed or has_error_event(response.text)
    if not ok:
        print(f"FAIL {label}: {response.status_code}\n{response.text[:500]}")
    else:
        print(f"OK   {label}: {response.status_code}")
    return ok


def main() -> int:
    token = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}
    thread = str(uuid.uuid4())

    cases: list[tuple[str, dict, dict, set[int]]] = [
        (
            "missing thread_id",
            {"message": "hello"},
            headers,
            {400, 422},
        ),
        (
            "non-uuid thread_id",
            {"thread_id": "not-a-uuid", "message": "hello"},
            headers,
            {400, 422},
        ),
        (
            "invalid resume shape",
            {"thread_id": thread, "resume": {"approved": "yes"}},
            headers,
            {400, 422},
        ),
        (
            "oversized message",
            {"thread_id": thread, "message": "x" * 50_000},
            headers,
            {400, 413, 422},
        ),
        (
            "invalid content-type",
            {"thread_id": thread, "message": "hello"},
            {**headers, "Content-Type": "text/plain"},
            {400, 415, 422},
        ),
        (
            "unicode bomb",
            {"thread_id": thread, "message": "\ufeff\u202e\u202d" * 1000},
            headers,
            {400, 422},
        ),
    ]

    passed = 0
    for label, body, hdrs, allowed in cases:
        r = httpx.post(
            f"{BASE}/agent/stream",
            json=body,
            headers=hdrs,
            timeout=10,
        )
        if check(label, r, allowed):
            passed += 1

    # Unauthenticated must be rejected without server crash.
    r = httpx.post(
        f"{BASE}/agent/stream",
        json={"thread_id": str(uuid.uuid4()), "message": "hello"},
        timeout=10,
    )
    if check("unauthenticated", r, {401, 403}):
        passed += 1
    else:
        cases.append(("unauthenticated", {}, {}, {401, 403}))  # for count

    total = len(cases)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
