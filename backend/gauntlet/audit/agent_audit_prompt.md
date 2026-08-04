# Agent Decision Trail Review

You are reviewing a structured trace of one HITL agent run from the Jidoka
backend. The trace follows the schema in `agent_audit_schema.json`.

## Input

You will receive a single JSON object representing one agent decision trail.

## Review axes

1. **Logical consistency**
   - Does the sequence of events follow a valid state machine?
   - A `tool_call` must precede a matching `proposed_changes` entry.
   - An `apply` event must follow an `approval_decision` of `approved`.
   - A `rejected` decision must not be followed by `applied_changes`.

2. **Spec adherence**
   - The first supported tool is `create_task` with arguments
     `title`, `description`, `column_id`, `project_id`, `checklist`.
   - `column_id` must be one of `backlog`, `todo`, `in_progress`, `done`.
   - `title` must be non-empty after trimming.
   - `project_id`, when present, must belong to the same user as the thread.
   - All events must include a `thread_id` and ISO-8601 `timestamp`.

3. **Rationale quality**
   - If the trace includes a model-generated rationale, evaluate whether it
     explains why the proposed change satisfies the user's message.
   - Flag rationale that is generic, contradictory, or missing when a
     non-trivial decision was made.

4. **Error handling**
   - `errors` must be non-empty when the run ended without a successful apply
     or a clean rejection.
   - Errors must be actionable: they should state what was invalid and why.

## Output format

Respond with a JSON object:

```json
{
  "verdict": "pass" | "warn" | "fail",
  "issues": [
    {
      "severity": "major" | "minor",
      "category": "logical_consistency" | "spec_adherence" | "rationale_quality" | "error_handling",
      "message": "concise description of the issue"
    }
  ],
  "summary": "one-paragraph overall assessment"
}
```

Use `warn` for minor deviations that do not break the protocol. Use `fail` for
any major inconsistency, unauthorized mutation, or spec violation.
