"use server";

import { revalidatePath } from "next/cache";
import {
  BACKEND_URL,
  toProject,
  toTask,
  type ApiProject,
  type ApiTask,
} from "@/lib/api";
import type { ColumnId, Project, Task } from "@/lib/types";

export async function createTask(input: {
  columnId: ColumnId;
  title: string;
  description?: string;
  projectId?: string;
}): Promise<Task> {
  const res = await fetch(`${BACKEND_URL}/tasks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      description: input.description ?? null,
      column_id: input.columnId,
      project_id: input.projectId ?? null,
    }),
  });
  if (!res.ok) {
    throw new Error(`POST /tasks failed: ${res.status}`);
  }
  const created: ApiTask = await res.json();
  revalidatePath("/board");
  return toTask(created);
}

export async function createProject(input: {
  name: string;
  description?: string;
}): Promise<Project> {
  const res = await fetch(`${BACKEND_URL}/projects`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? null,
    }),
  });
  if (!res.ok) {
    throw new Error(`POST /projects failed: ${res.status}`);
  }
  const created: ApiProject = await res.json();
  revalidatePath("/");
  // AddTaskDialog reads the project list as a server-fetched prop on the
  // board page, so it needs a refresh too or a project created here
  // wouldn't be selectable there until an unrelated navigation refreshed it.
  revalidatePath("/board");
  return toProject(created);
}

export async function updateProject(input: {
  id: string;
  name: string;
  description?: string;
}): Promise<Project> {
  const res = await fetch(
    `${BACKEND_URL}/projects/${encodeURIComponent(input.id)}`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: input.name,
        description: input.description ?? null,
      }),
    },
  );
  if (!res.ok) {
    throw new Error(`PATCH /projects/${input.id} failed: ${res.status}`);
  }
  const updated: ApiProject = await res.json();
  revalidatePath("/");
  revalidatePath("/board");
  return toProject(updated);
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/projects/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`DELETE /projects/${id} failed: ${res.status}`);
  }
  revalidatePath("/");
  // A deleted project unlinks (not deletes) its tasks server-side, so the
  // board's project select needs a refresh to drop it from the options.
  revalidatePath("/board");
}

export async function moveTask(input: {
  taskId: string;
  columnId: ColumnId;
  position: number;
}): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(input.taskId)}/move`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        column_id: input.columnId,
        position: input.position,
      }),
    },
  );
  if (!res.ok) {
    throw new Error(`PATCH /tasks/${input.taskId}/move failed: ${res.status}`);
  }
  revalidatePath("/board");
}

// Persist a completed pomodoro work block. No revalidatePath: the board
// doesn't render time data yet, so there is nothing to refresh. Stopped
// (aborted) focus sessions are never sent here - only finished ones count.
export async function recordWorkBlock(input: {
  taskId: string;
  startedAt: number; // epoch ms
  endedAt: number; // epoch ms
}): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(input.taskId)}/work-blocks`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        started_at: new Date(input.startedAt).toISOString(),
        ended_at: new Date(input.endedAt).toISOString(),
      }),
    },
  );
  if (!res.ok) {
    throw new Error(
      `POST /tasks/${input.taskId}/work-blocks failed: ${res.status}`,
    );
  }
}

export async function logWorkBlock(input: {
  taskId: string;
  minutes: number;
}): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(input.taskId)}/work-blocks`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ minutes: input.minutes }),
    },
  );
  if (!res.ok) {
    throw new Error(
      `POST /tasks/${input.taskId}/work-blocks failed: ${res.status}`,
    );
  }
}

// Sum of a task's persisted work_blocks minutes, for the task detail dialog.
// create_work_block always fills in `minutes` server-side (from the payload
// or computed from started_at/ended_at), so a plain sum is enough here.
export async function fetchTaskMinutes(taskId: string): Promise<number> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(taskId)}/work-blocks`,
    { cache: "no-store" },
  );
  if (!res.ok) {
    throw new Error(
      `GET /tasks/${taskId}/work-blocks failed: ${res.status}`,
    );
  }
  const blocks: { minutes: number | null }[] = await res.json();
  return blocks.reduce((total, b) => total + (b.minutes ?? 0), 0);
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(taskId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`DELETE /tasks/${taskId} failed: ${res.status}`);
  }
  revalidatePath("/board");
}
