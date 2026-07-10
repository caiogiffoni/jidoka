export const COLUMNS = [
  { id: "todo", title: "To Do" },
  { id: "in_progress", title: "In Progress" },
  { id: "done", title: "Done" },
] as const;

export type ColumnId = (typeof COLUMNS)[number]["id"];

export function isColumnId(id: unknown): id is ColumnId {
  return COLUMNS.some((c) => c.id === id);
}

export interface Task {
  id: string;
  title: string;
  description?: string;
}

// Array order within a column is the display order; the backend persists it
// as a `position` field per task.
export type TasksByColumn = Record<ColumnId, Task[]>;
