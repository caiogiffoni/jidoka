"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { Task } from "@/lib/types";

export function TaskDialog({
  task,
  open,
  onOpenChange,
}: {
  task: Task;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="pr-6 leading-snug">{task.title}</DialogTitle>
        </DialogHeader>
        {task.description ? (
          <p className="text-sm whitespace-pre-wrap text-muted-foreground">
            {task.description}
          </p>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            No description
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
