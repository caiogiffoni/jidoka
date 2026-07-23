import { beforeEach, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";

vi.mock("@/app/actions", () => ({
  deleteTask: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

import { toast } from "sonner";
import { deleteTask } from "@/app/actions";
import { useBoardStore } from "@/stores/board-store";
import { deleteTaskWithUndo } from "./delete-task";
import type { Task } from "@/lib/types";

const task: Task = { id: "a", title: "Task A" };

interface ToastOptions {
  action: { onClick: () => void };
  onAutoClose: () => void;
}

function lastToastOptions(): ToastOptions {
  const calls = vi.mocked(toast).mock.calls;
  return calls[calls.length - 1][1] as unknown as ToastOptions;
}

beforeEach(() => {
  useBoardStore.setState({
    tasks: { backlog: [], todo: [task], in_progress: [], done: [] },
  });
  vi.mocked(deleteTask).mockReset().mockResolvedValue(undefined);
  vi.mocked(toast).mockClear();
  vi.mocked(toast.error).mockClear();
});

it("optimistically removes the task immediately", () => {
  deleteTaskWithUndo(task);
  expect(useBoardStore.getState().tasks.todo).toHaveLength(0);
});

it("commits the server delete when the toast auto-closes", () => {
  deleteTaskWithUndo(task);
  lastToastOptions().onAutoClose();
  expect(deleteTask).toHaveBeenCalledWith("a");
});

it("restores the task and skips the server delete when undo is clicked first", () => {
  deleteTaskWithUndo(task);
  const options = lastToastOptions();

  options.action.onClick();
  expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual(["a"]);

  // the toast closing afterward must not also fire the delete
  options.onAutoClose();
  expect(deleteTask).not.toHaveBeenCalled();
});

it("restores the task and shows an error toast if the server delete fails", async () => {
  vi.mocked(deleteTask).mockRejectedValueOnce(new Error("network"));
  deleteTaskWithUndo(task);
  lastToastOptions().onAutoClose();

  await waitFor(() => {
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "a",
    ]);
  });
  expect(toast.error).toHaveBeenCalled();
});
