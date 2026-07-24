import type { ColumnId } from "./types";

// Appending a bare time (no "Z"/offset) parses in the browser's local
// timezone, matching how the date-only string is meant to read - parsing
// the ISO date alone would parse as UTC midnight and could read as the
// wrong day depending on the viewer's timezone.
function toLocalDate(isoDate: string): Date {
  return new Date(`${isoDate}T00:00:00`);
}

// A due date only counts as overdue once its day has fully passed, and
// never for a card already in Done - finishing late is still finishing.
export function isOverdue(
  dueDate: string | undefined,
  columnId: ColumnId | undefined,
): boolean {
  if (!dueDate || columnId === "done") return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return toLocalDate(dueDate) < today;
}

export function formatDueDate(dueDate: string): string {
  return toLocalDate(dueDate).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
