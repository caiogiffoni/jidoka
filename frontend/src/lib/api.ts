import type { ColumnId, Project, Task, TasksByColumn } from "./types";

// Server-side only: Server Components and Server Actions proxy to FastAPI,
// which is the single writer to Postgres. The browser never calls it directly.
export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export interface ApiTask {
  id: string;
  title: string;
  description: string | null;
  column_id: ColumnId;
  position: number;
  project_id: string | null;
}

export function toTask(t: ApiTask): Task {
  return {
    id: t.id,
    title: t.title,
    description: t.description ?? undefined,
    projectId: t.project_id ?? undefined,
  };
}

export interface ApiProject {
  id: string;
  name: string;
  created_at: string;
}

export function toProject(p: ApiProject): Project {
  return { id: p.id, name: p.name, createdAt: p.created_at };
}

export async function fetchProjects(): Promise<Project[]> {
  try {
    const res = await fetch(`${BACKEND_URL}/projects`, { cache: "no-store" });
    if (!res.ok) throw new Error(`GET /projects failed: ${res.status}`);
    const apiProjects: ApiProject[] = await res.json();
    return apiProjects.map(toProject);
  } catch (error) {
    console.error("Could not load projects from backend:", error);
    return [];
  }
}

export interface ApiDailyProjectMinutes {
  date: string;
  project_id: string | null;
  project_name: string | null;
  minutes: number;
}

export async function fetchDailyStats(
  days = 7,
): Promise<ApiDailyProjectMinutes[]> {
  try {
    const res = await fetch(
      `${BACKEND_URL}/work-blocks/stats/daily?days=${days}`,
      { cache: "no-store" },
    );
    if (!res.ok) {
      throw new Error(`GET /work-blocks/stats/daily failed: ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error("Could not load daily stats from backend:", error);
    return [];
  }
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
