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
