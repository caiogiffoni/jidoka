import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/app/actions", () => ({
  createTask: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

import { createTask } from "@/app/actions";
import { useBoardStore } from "@/stores/board-store";
import { AddTaskDialog } from "./add-task-dialog";
import type { Project, Task } from "@/lib/types";

const projects: Project[] = [
  { id: "p1", name: "Alpha", createdAt: "2026-01-01T00:00:00Z" },
];

beforeEach(() => {
  useBoardStore.setState({
    tasks: { backlog: [], todo: [], in_progress: [], done: [] },
  });
  vi.mocked(createTask).mockReset();
});

it("submits the trimmed title, chosen project, and selected column", async () => {
  const user = userEvent.setup();
  const created: Task = { id: "t1", title: "Write docs", projectId: "p1" };
  vi.mocked(createTask).mockResolvedValue(created);

  render(<AddTaskDialog projects={projects} />);
  await user.click(screen.getByRole("button", { name: "Add task" }));

  const dialog = within(await screen.findByRole("dialog"));
  await user.type(dialog.getByLabelText("Title"), "  Write docs  ");
  await user.selectOptions(dialog.getByLabelText(/project/i), "p1");
  await user.click(dialog.getByRole("button", { name: "In Progress" }));
  await user.click(dialog.getByRole("button", { name: "Add task" }));

  expect(createTask).toHaveBeenCalledWith({
    columnId: "in_progress",
    title: "Write docs",
    description: undefined,
    projectId: "p1",
  });
  expect(useBoardStore.getState().tasks.in_progress).toEqual([created]);
});

it("keeps the dialog open and leaves the store untouched when the save fails", async () => {
  const user = userEvent.setup();
  vi.mocked(createTask).mockRejectedValue(new Error("network"));

  render(<AddTaskDialog projects={projects} />);
  await user.click(screen.getByRole("button", { name: "Add task" }));

  const dialog = within(await screen.findByRole("dialog"));
  await user.type(dialog.getByLabelText("Title"), "Broken");
  await user.click(dialog.getByRole("button", { name: "Add task" }));

  await screen.findByRole("dialog"); // still open after the rejection
  expect(useBoardStore.getState().tasks.todo).toHaveLength(0);
});
