# QA-Fxx — Agent chat panel (HITL create_task)

Manual QA from a browser user's perspective. Backend, Postgres, and frontend
(`pnpm dev`) must be running.

## Setup

1. Log in to Jidoka.
2. Navigate to `/board`.

## Steps

1. **Open the agent chat panel**

   Click the violet agent button in the board header (next to "Add task").

   **Expected:** A slide-over panel opens from the right with a message list,
   an input field, and a Send button.

2. **Send a create-task request**

   Type "Add a task called wire HITL flow to todo" and press Send.

   **Expected:**
   - Your message appears in the chat history.
   - A streaming indicator appears briefly.
   - A proposed diff card appears showing the task title, column, and an
     Approve/Reject button pair.

3. **Approve the diff**

   Click **Approve**.

   **Expected:**
   - The diff card disappears.
   - A success indicator or applied-event summary appears.
   - The new card "wire HITL flow" appears in the "To Do" column without a
     page refresh.

4. **Reject a diff**

   Send "Add a task called rejected idea" and click **Reject** on the diff.

   **Expected:**
   - The diff card disappears.
   - No new card appears on the board.

## Unhappy paths to verify

- **Empty input:** Send an empty message → the Send button is disabled or
  nothing happens.
- **Offline/network failure:** Stop the backend, send a message → an error
  message appears in the panel; the board is unchanged.
- **Unauthenticated:** Clear cookies or wait for token expiry, open the panel,
  send a message → the user is redirected to `/login`.
- **Rapid approve/reject:** Click Approve twice quickly → only one task is
  created.

## State verification

- `GET /tasks` (via browser dev tools network tab) returns the approved task
  with the correct `column_id` and `user_id`.
- Rejected tasks never appear in the `/tasks` response.
