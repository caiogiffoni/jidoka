export const COLUMNS = [
  { id: "backlog", title: "Backlog" },
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
  projectId?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
}

// Array order within a column is the display order; the backend persists it
// as a `position` field per task.
export type TasksByColumn = Record<ColumnId, Task[]>;
