# History

Running session log, newest first.

## 2026-10-13 - Code review + agent/board robustness fixes

**Landed** (three PRs, merged in order):

- #9 `fix/agent-robustness`: tool errors are answered with an error `ToolMessage` instead of leaving a dangling tool_call (which 400'd every later turn); Postgres checkpointer replaces `MemorySaver`; threads keyed server-side as `<user_id>:<thread_id>`; `apply` is all-or-nothing in one transaction (services gained `commit=False`); a resume with nothing pending returns an error instead of starting an empty turn.
- #8 `fix/board-refresh-sync`: the board store resyncs from server props, so `router.refresh()` (agent apply, archive restore, daily generation) reaches the board; Escape mid-drag restores the card.
- #7 `fix/agent-chat-streaming`: real incremental SSE parsing, `res.ok` checks, approve/reject keep the diff until accepted, abort on unmount, and a stable per-board `thread_id`.

- #10 `fix/auth-hardening`: 72-byte password cap (422/401, never 500), lowercase + case-insensitive emails, register race → 409, rate limits keyed on the forwarded client IP (trusted only with `INTERNAL_PROXY_SECRET`), per-user keys on user-scoped routes, per-email failed-login limit.
- #11 `fix/oauth-security`: no OAuth auto-linking by email (closes pre-registration takeover), provider-verified email required for new accounts, `state` bound to the browser via cookie (login CSRF), `typ` claims on state/access tokens, JWT replaced in the redirect URL by a 60s single-use exchange code. Merged after resolving a one-line import conflict with #10 in `actions.ts`.
- `deploy.yml` gained a `concurrency` group: the three back-to-back deploys after #9/#8/#7 collided on the EC2 host and all failed (#10's deploy succeeded and carried them).

**Decisions:** fixes split into three packs on separate branches to avoid conflicts; backend merged first because a constant client `thread_id` is only safe once threads are user-scoped server-side.

**Deploy to-dos:** set `INTERNAL_PROXY_SECRET` (same value) on Vercel and the EC2 host; confirm the backend's `BACKEND_URL` is its public https URL. The real-LLM test `test_real_llm_title_and_column_proposes_task` flaked once on CI (passed on rerun).

**Next:** the remaining findings listed in CLAUDE.md ("Open findings from the 2026-10-13 code review"); chat history reload endpoint; `AGENTS.md` is stale (still says the agent isn't built).
