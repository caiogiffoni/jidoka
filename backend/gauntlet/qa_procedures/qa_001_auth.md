# QA-001 — Auth lifecycle

Manual QA from an API consumer's perspective against `http://localhost:8000`.
Requires `jq` for token capture. Backend and Postgres must be running
(`docker compose up -d`).

## Steps

1. Register a new user and capture the token:

   ```bash
   curl -s -X POST http://localhost:8000/auth/register \
     -H 'Content-Type: application/json' \
     -d '{"email":"qa-auth@example.com","username":"qaauth","password":"Password1!"}' | tee /tmp/reg.json
   TOKEN=$(jq -r .token /tmp/reg.json)
   ```

   **Expected:** HTTP 201. Body has `user.id`, `user.email`, `user.username`,
   and a non-empty `token`. No `hashed_password` field anywhere in the body.

2. Call `me` with the registration token:

   ```bash
   curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 200 with `email: "qa-auth@example.com"`,
   `username: "qaauth"`, and a `created_at` timestamp.

3. Log in with the same credentials and capture the new token:

   ```bash
   curl -s -X POST http://localhost:8000/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"email":"qa-auth@example.com","password":"Password1!"}' | tee /tmp/login.json
   TOKEN=$(jq -r .token /tmp/login.json)
   ```

   **Expected:** HTTP 200, fresh `token`, same `user` payload as step 1.

4. Call `me` with the login token:

   ```bash
   curl -s http://localhost:8000/auth/me -H "Authorization: Bearer $TOKEN"
   ```

   **Expected:** HTTP 200, same identity as step 2.

5. Logout:

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/auth/logout
   ```

   **Expected:** HTTP 204. (Logout is client-side; the token keeps working.)

## Unhappy paths to verify

- Wrong password → 401:
  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/auth/login \
    -H 'Content-Type: application/json' \
    -d '{"email":"qa-auth@example.com","password":"WrongPass1!"}'
  ```
- Unknown email → 401 (same shape as wrong password; no user enumeration).
- Duplicate email (register again with `qa-auth@example.com`, different
  username) → 409 with `detail` mentioning email.
- Duplicate username (register with `qaauth`, different email) → 409 with
  `detail` mentioning username.
- Weak password (`"Password1"` — no special character, or shorter than 8
  chars) → 422.
- Invalid username (`"1starts_with_digit"`, or fewer than 3 chars) → 422.
- `GET /auth/me` with no `Authorization` header → 401 or 403.
- `GET /auth/me` with `Authorization: Bearer not-a-token` → 401.
