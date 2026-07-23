"use client";

import { toast } from "sonner";
import { useBoardStore } from "@/stores/board-store";
import { archiveTask } from "@/app/actions";
import type { Task } from "@/lib/types";

// Same optimistic-remove-plus-undo-toast shape as deleteTaskWithUndo (see
// delete-task.tsx): the server archive waits for the toast to close, and
// undo just restores the store with no round-trip to take back.
export function archiveTaskWithUndo(task: Task) {
  const state = useBoardStore.getState();
  const column = state.columnOf(task.id);
  if (!column) return;
  const index = state.tasks[column].findIndex((t) => t.id === task.id);

  state.removeTask(task.id);

  let finished = false;
  const commit = () => {
    if (finished) return;
    finished = true;
    archiveTask(task.id).catch((error) => {
      console.error("Could not archive task:", error);
      useBoardStore.getState().restoreTask(task, column, index);
      toast.error("Couldn't archive the task", {
        description: "The card was put back. Try again.",
      });
    });
  };

  toast("Task archived", {
    description: task.title,
    action: {
      label: "Undo",
      onClick: () => {
        finished = true;
        useBoardStore.getState().restoreTask(task, column, index);
      },
    },
    onAutoClose: commit,
    onDismiss: commit,
  });
}
