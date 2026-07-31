"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { revalidatePath } from "next/cache";
import {
  AUTH_COOKIE,
  authHeaders,
  BACKEND_URL,
  toProject,
  toTask,
  type ApiProject,
  type ApiTask,
} from "@/lib/api";
import type {
  ChecklistItem,
  ColumnId,
  DailyTemplate,
  Project,
  Task,
  User,
} from "@/lib/types";

async function apiFetch(input: string, init: RequestInit = {}) {
  const headers: Record<string, string> = {
    ...(await authHeaders()),
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  return fetch(input, { ...init, headers });
}

function dailyTemplateBody(template: DailyTemplate | null | undefined) {
  if (!template) return null;
  return {
    title: template.title ?? null,
    description: template.description ?? null,
    checklist: template.checklist,
  };
}

export async function createTask(input: {
  columnId: ColumnId;
  title: string;
  description?: string;
  projectId?: string;
  checklist?: ChecklistItem[];
}): Promise<Task> {
  const res = await apiFetch(`${BACKEND_URL}/tasks`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      title: input.title,
      description: input.description ?? null,
      column_id: input.columnId,
      project_id: input.projectId ?? null,
      checklist: input.checklist ?? [],
    }),
  });
  if (!res.ok) {
    throw new Error(`POST /tasks failed: ${res.status}`);
  }
  const created: ApiTask = await res.json();
  revalidatePath("/board");
  return toTask(created);
}

// PATCH /tasks/{id} is a full replace, so every call must carry the task's
// complete state - including the checklist - not just the fields the caller
// means to change, or it'll silently wipe the rest (e.g. the checklist, if a
// title/description edit forgot to pass it through).
export async function updateTask(input: {
  taskId: string;
  title: string;
  description?: string;
  projectId?: string;
  checklist?: ChecklistItem[];
  dueDate?: string;
}): Promise<Task> {
  const res = await apiFetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(input.taskId)}`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        title: input.title,
        description: input.description ?? null,
        project_id: input.projectId ?? null,
        checklist: input.checklist ?? [],
        due_date: input.dueDate ?? null,
      }),
    },
  );
  if (!res.ok) {
    throw new Error(`PATCH /tasks/${input.taskId} failed: ${res.status}`);
  }
  const updated: ApiTask = await res.json();
  revalidatePath("/board");
  // A project reassignment shifts the dashboard's per-project task counts.
  revalidatePath("/");
  return toTask(updated);
}

export async function createProject(input: {
  name: string;
  description?: string;
  dailyEnabled?: boolean;
  dailyTemplate?: DailyTemplate | null;
}): Promise<Project> {
  const res = await apiFetch(`${BACKEND_URL}/projects`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? null,
      daily_enabled: input.dailyEnabled ?? false,
      daily_template: dailyTemplateBody(input.dailyTemplate),
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

// PATCH /projects/{id} is a full replace (like PATCH /tasks/{id}), so every
// call must carry the project's complete state - including the daily
// template - not just the fields the caller means to change.
export async function updateProject(input: {
  id: string;
  name: string;
  description?: string;
  dailyEnabled?: boolean;
  dailyTemplate?: DailyTemplate | null;
}): Promise<Project> {
  const res = await apiFetch(
    `${BACKEND_URL}/projects/${encodeURIComponent(input.id)}`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: input.name,
        description: input.description ?? null,
        daily_enabled: input.dailyEnabled ?? false,
        daily_template: dailyTemplateBody(input.dailyTemplate),
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

// Generates today's checklist card for each daily-enabled project. Called
// once per browser-local calendar day by DailyTaskGenerator (mounted in the
// root layout) - idempotent server-side per UTC day, so redundant calls are
// harmless no-ops. Silently skips when there is no session (e.g. on /login).
export async function generateDailyTasks(): Promise<{ created: number }> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  if (!token) {
    return { created: 0 };
  }

  const res = await apiFetch(`${BACKEND_URL}/projects/daily-tasks/generate`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`POST /projects/daily-tasks/generate failed: ${res.status}`);
  }
  const created: ApiTask[] = await res.json();
  if (created.length > 0) {
    revalidatePath("/board");
    revalidatePath("/");
  }
  return { created: created.length };
}

export async function deleteProject(id: string): Promise<void> {
  const res = await apiFetch(
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
  const res = await apiFetch(
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
  const res = await apiFetch(
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
  const res = await apiFetch(
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
  const res = await apiFetch(
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
  const res = await apiFetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(taskId)}`,
    { method: "DELETE" },
  );
  if (!res.ok) {
    throw new Error(`DELETE /tasks/${taskId} failed: ${res.status}`);
  }
  revalidatePath("/board");
}

export async function archiveTask(
  taskId: string,
  archived = true,
): Promise<void> {
  const res = await apiFetch(
    `${BACKEND_URL}/tasks/${encodeURIComponent(taskId)}/archive`,
    {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ archived }),
    },
  );
  if (!res.ok) {
    throw new Error(`PATCH /tasks/${taskId}/archive failed: ${res.status}`);
  }
  revalidatePath("/board");
}

export async function fetchArchivedTasks(): Promise<Task[]> {
  const res = await apiFetch(`${BACKEND_URL}/tasks?include_archived=true`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`GET /tasks?include_archived=true failed: ${res.status}`);
  }
  const apiTasks: ApiTask[] = await res.json();
  return apiTasks.filter((t) => t.archived).map(toTask);
}

export type AuthActionState =
  | { type: "error"; message: string }
  | { type: "success"; message: string };

function backendErrorMessage(res: Response, fallback: string): string {
  // FastAPI returns { detail: ... } for 4xx errors. Pydantic validation errors
  // use a list of loc/msg dicts; fall back to the generic message otherwise.
  try {
    const data = res.json() as unknown;
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      typeof data.detail === "string"
    ) {
      return data.detail;
    }
    if (
      typeof data === "object" &&
      data !== null &&
      "detail" in data &&
      Array.isArray(data.detail) &&
      data.detail.length > 0 &&
      typeof data.detail[0].msg === "string"
    ) {
      return data.detail[0].msg;
    }
  } catch {
    // ignore parse failures
  }
  return fallback;
}

async function setAuthCookie(token: string) {
  const cookieStore = await cookies();
  cookieStore.set(AUTH_COOKIE, token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 60 * 60 * 24 * 7, // 7 days
    path: "/",
  });
}

export async function login(
  _prevState: AuthActionState | null,
  formData: FormData,
): Promise<AuthActionState | null> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  if (!email || !password) {
    return { type: "error", message: "Please enter both email and password." };
  }

  const res = await fetch(`${BACKEND_URL}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    return {
      type: "error",
      message: backendErrorMessage(res, "Invalid email or password."),
    };
  }

  const { token }: { token: string } = await res.json();
  await setAuthCookie(token);
  redirect("/board");
}

export async function register(
  _prevState: AuthActionState | null,
  formData: FormData,
): Promise<AuthActionState | null> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");
  const confirmPassword = String(formData.get("confirmPassword") ?? "");
  if (!email || !password) {
    return { type: "error", message: "Please enter both email and password." };
  }
  if (password.length < 8) {
    return { type: "error", message: "Password must be at least 8 characters." };
  }
  if (!/[^A-Za-z0-9\s]/.test(password)) {
    return {
      type: "error",
      message: "Password must contain at least one special character.",
    };
  }
  if (password !== confirmPassword) {
    return { type: "error", message: "Passwords do not match." };
  }

  const res = await fetch(`${BACKEND_URL}/auth/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, username: email.split("@")[0], password }),
  });
  if (!res.ok) {
    return {
      type: "error",
      message: backendErrorMessage(res, "Could not create account."),
    };
  }

  const { token }: { token: string } = await res.json();
  await setAuthCookie(token);
  redirect("/board");
}

export async function logout(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(AUTH_COOKIE);
  redirect("/login");
}

export async function requireAuth(): Promise<User> {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_COOKIE)?.value;
  if (!token) {
    redirect("/login");
  }

  const res = await fetch(`${BACKEND_URL}/auth/me`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    redirect("/login");
  }

  return (await res.json()) as User;
}
