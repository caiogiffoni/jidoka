import { beforeEach, expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";

vi.mock("@/app/actions", () => ({
  archiveTask: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

import { toast } from "sonner";
import { archiveTask } from "@/app/actions";
import { useBoardStore } from "@/stores/board-store";
import { archiveTaskWithUndo } from "./archive-task";
import type { Task } from "@/lib/types";

const task: Task = { id: "a", title: "Task A", checklist: [] };

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
  vi.mocked(archiveTask).mockReset().mockResolvedValue(undefined);
  vi.mocked(toast).mockClear();
  vi.mocked(toast.error).mockClear();
});

it("optimistically removes the task immediately", () => {
  archiveTaskWithUndo(task);
  expect(useBoardStore.getState().tasks.todo).toHaveLength(0);
});

it("commits the server archive when the toast auto-closes", () => {
  archiveTaskWithUndo(task);
  lastToastOptions().onAutoClose();
  expect(archiveTask).toHaveBeenCalledWith("a");
});

it("restores the task and skips the server archive when undo is clicked first", () => {
  archiveTaskWithUndo(task);
  const options = lastToastOptions();

  options.action.onClick();
  expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual(["a"]);

  // the toast closing afterward must not also fire the archive
  options.onAutoClose();
  expect(archiveTask).not.toHaveBeenCalled();
});

it("restores the task and shows an error toast if the server archive fails", async () => {
  vi.mocked(archiveTask).mockRejectedValueOnce(new Error("network"));
  archiveTaskWithUndo(task);
  lastToastOptions().onAutoClose();

  await waitFor(() => {
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "a",
    ]);
  });
  expect(toast.error).toHaveBeenCalled();
});
