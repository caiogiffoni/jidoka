"""Race two concurrent messages on the same thread_id."""

import asyncio
import json
import sys
import uuid

import httpx

BASE = "http://localhost:8000"


def parse_sse_events(text: str) -> list[dict]:
    events = []
    current = {}
    for line in text.split("\n"):
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current.setdefault("data", []).append(line[len("data:") :].strip())
        elif line == "" and current:
            current["data"] = json.loads("".join(current["data"])) if current.get("data") else {}
            events.append(current)
            current = {}
    if current:
        current["data"] = json.loads("".join(current["data"])) if current.get("data") else {}
        events.append(current)
    return events


def register_and_login() -> str:
    email = f"race-{uuid.uuid4().hex[:8]}@example.com"
    username = f"race{uuid.uuid4().hex[:8]}"
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


async def post_stream(client: httpx.AsyncClient, token: str, body: dict) -> httpx.Response:
    return await client.post(
        f"{BASE}/agent/stream",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


async def main() -> int:
    token = register_and_login()
    thread_id = str(uuid.uuid4())
    body = {"thread_id": thread_id, "message": "Add two tasks concurrently"}

    async with httpx.AsyncClient() as client:
        responses = await asyncio.gather(
            post_stream(client, token, body),
            post_stream(client, token, body),
            return_exceptions=True,
        )

    ok = True
    for idx, r in enumerate(responses):
        if isinstance(r, Exception):
            print(f"FAIL request {idx}: {r}")
            ok = False
            continue
        print(f"request {idx}: {r.status_code}")
        if r.status_code not in {200, 409, 423}:
            print(f"FAIL request {idx}: unexpected status\n{r.text[:500]}")
            ok = False

    if not ok:
        return 1

    # Approve whatever interrupt (if any) is current for the thread.
    async with httpx.AsyncClient() as client:
        r = await post_stream(
            client,
            token,
            {"thread_id": thread_id, "resume": {"approved": True}},
        )

    print(f"approve: {r.status_code}")
    if r.status_code != 200:
        print(r.text[:500])
        return 1

    events = parse_sse_events(r.text)
    created = sum(
        len(e["data"].get("created_tasks", []))
        for e in events
        if e["event"] == "apply"
    )

    # Verify board state: no crash and no phantom duplicates.
    r = httpx.get(f"{BASE}/tasks", headers={"Authorization": f"Bearer {token}"})
    tasks = r.json()
    titles = [t["title"] for t in tasks]
    duplicates = len(titles) - len(set(titles))

    print(f"created via apply events: {created}")
    print(f"duplicate titles on board: {duplicates}")

    if duplicates > 0:
        print("FAIL duplicate tasks found")
        return 1

    print("OK   race behavior is defined")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
