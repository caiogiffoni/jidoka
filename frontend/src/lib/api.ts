import type { ColumnId, Task, TasksByColumn } from "./types";

// Server-side only: Server Components and Server Actions proxy to FastAPI,
// which is the single writer to Postgres. The browser never calls it directly.
export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export interface ApiTask {
  id: string;
  title: string;
  description: string | null;
  column_id: ColumnId;
  position: number;
}

export function toTask(t: ApiTask): Task {
  return { id: t.id, title: t.title, description: t.description ?? undefined };
}

export async function fetchTasksByColumn(): Promise<TasksByColumn> {
  const grouped: TasksByColumn = { todo: [], in_progress: [], done: [] };

  let apiTasks: ApiTask[];
  try {
    const res = await fetch(`${BACKEND_URL}/tasks`, { cache: "no-store" });
    if (!res.ok) throw new Error(`GET /tasks failed: ${res.status}`);
    apiTasks = await res.json();
  } catch (error) {
    // Backend down: render an empty board instead of crashing the page.
    console.error("Could not load tasks from backend:", error);
    return grouped;
  }

  for (const t of apiTasks) {
    grouped[t.column_id]?.push(toTask(t));
  }
  return grouped;
}
