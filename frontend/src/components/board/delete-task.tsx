"use client";

import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useBoardStore } from "@/stores/board-store";
import { deleteTask } from "@/app/actions";
import type { Task } from "@/lib/types";

// Optimistically remove the task and show an undo toast. The server delete
// waits for the toast to close: undo just restores the store, so there is
// no round-trip to take back. If the page is closed while the toast is
// still up, the delete is never sent and the card survives the reload.
export function deleteTaskWithUndo(task: Task) {
  const state = useBoardStore.getState();
  const column = state.columnOf(task.id);
  if (!column) return;
  const index = state.tasks[column].findIndex((t) => t.id === task.id);

  state.removeTask(task.id);

  let finished = false;
  const commit = () => {
    if (finished) return;
    finished = true;
    deleteTask(task.id).catch((error) => {
      console.error("Could not delete task:", error);
      useBoardStore.getState().restoreTask(task, column, index);
      toast.error("Couldn't delete the task", {
        description: "The card was put back. Try again.",
      });
    });
  };

  toast("Task deleted", {
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

export function ConfirmDeleteDialog({
  task,
  open,
  onOpenChange,
  onConfirm,
}: {
  task: Task;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm?: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xs">
        <DialogHeader>
          <DialogTitle>Delete task?</DialogTitle>
          <DialogDescription>
            &ldquo;{task.title}&rdquo; will be removed from the board. You can
            undo right after.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              // Close the dialogs before the store removal unmounts them.
              onOpenChange(false);
              onConfirm?.();
              deleteTaskWithUndo(task);
            }}
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
