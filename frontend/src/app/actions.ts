"use server";

import { revalidatePath } from "next/cache";
import { BACKEND_URL, toTask, type ApiTask } from "@/lib/api";
import type { ColumnId, Task } from "@/lib/types";

export async function createTask(input: {
  columnId: ColumnId;
  title: string;
  description?: string;
}): Promise<Task> {
  const res = await fetch(`${BACKEND_URL}/tasks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      description: input.description ?? null,
      column_id: input.columnId,
    }),
  });
  if (!res.ok) {
    throw new Error(`POST /tasks failed: ${res.status}`);
  }
  const created: ApiTask = await res.json();
  revalidatePath("/");
  return toTask(created);
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
  revalidatePath("/");
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await fetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(taskId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`DELETE /tasks/${taskId} failed: ${res.status}`);
  }
  revalidatePath("/");
}
