import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/app/actions", () => ({
  archiveTask: vi.fn(),
  fetchArchivedTasks: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { toast } from "sonner";
import { archiveTask, fetchArchivedTasks } from "@/app/actions";
import { ArchivedTasksDialog } from "./archived-tasks-dialog";
import type { Task } from "@/lib/types";

const archivedTasks: Task[] = [
  { id: "t1", title: "Old idea", checklist: [], archived: true },
  { id: "t2", title: "Shelved task", checklist: [], archived: true },
];

beforeEach(() => {
  vi.mocked(archiveTask).mockReset().mockResolvedValue(undefined);
  vi.mocked(fetchArchivedTasks).mockReset().mockResolvedValue(archivedTasks);
  vi.mocked(toast.error).mockClear();
  vi.mocked(toast.success).mockClear();
});

it("loads and lists archived tasks when opened", async () => {
  const user = userEvent.setup();
  render(<ArchivedTasksDialog />);

  await user.click(screen.getByRole("button", { name: "Archived tasks" }));
  const dialog = within(await screen.findByRole("dialog"));

  expect(fetchArchivedTasks).toHaveBeenCalled();
  expect(dialog.getByText("Old idea")).toBeInTheDocument();
  expect(dialog.getByText("Shelved task")).toBeInTheDocument();
});

it("restores a task and removes it from the list", async () => {
  const user = userEvent.setup();
  render(<ArchivedTasksDialog />);

  await user.click(screen.getByRole("button", { name: "Archived tasks" }));
  const dialog = within(await screen.findByRole("dialog"));

  await user.click(dialog.getByRole("button", { name: /Restore Old idea/i }));

  expect(archiveTask).toHaveBeenCalledWith("t1", false);
  expect(dialog.queryByText("Old idea")).not.toBeInTheDocument();
  expect(dialog.getByText("Shelved task")).toBeInTheDocument();
  expect(toast.success).toHaveBeenCalled();
});

it("shows an error toast when loading fails", async () => {
  const user = userEvent.setup();
  vi.mocked(fetchArchivedTasks).mockRejectedValueOnce(new Error("network"));
  render(<ArchivedTasksDialog />);

  await user.click(screen.getByRole("button", { name: "Archived tasks" }));
  await screen.findByRole("dialog");

  expect(toast.error).toHaveBeenCalled();
});

it("shows an empty state when there are no archived tasks", async () => {
  const user = userEvent.setup();
  vi.mocked(fetchArchivedTasks).mockResolvedValueOnce([]);
  render(<ArchivedTasksDialog />);

  await user.click(screen.getByRole("button", { name: "Archived tasks" }));
  const dialog = within(await screen.findByRole("dialog"));

  expect(dialog.getByText("No archived tasks.")).toBeInTheDocument();
});
