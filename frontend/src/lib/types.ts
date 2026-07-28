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

export interface ChecklistItem {
  text: string;
  checked: boolean;
}

export interface Task {
  id: string;
  title: string;
  description?: string;
  projectId?: string;
  checklist: ChecklistItem[];
  // ISO "YYYY-MM-DD", no time component.
  dueDate?: string;
  archived?: boolean;
}

// Drafted through a popup styled like the real "Add task" dialog (see
// DailyTemplateDialog), but title/description/checklist are the only real
// fields - that popup's Project/Column controls are display-only. `title`
// is optional: the generated card is always named after the project and
// date, with this appended - not a replacement for that name.
export interface DailyTemplate {
  title?: string;
  description?: string;
  checklist: string[];
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  // Daily task generation: when enabled, the template is cloned into a
  // single card generated once per day (see generateDailyTasks in
  // app/actions.ts). Null until a template has actually been saved.
  dailyEnabled: boolean;
  dailyTemplate: DailyTemplate | null;
}

// Array order within a column is the display order; the backend persists it
// as a `position` field per task.
export type TasksByColumn = Record<ColumnId, Task[]>;

export interface User {
  id: string;
  email: string;
  username: string;
  createdAt: string;
}
