"use client";

import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useBoardStore } from "@/stores/board-store";
import { logWorkBlock } from "@/app/actions";
import { COLUMNS, type Task } from "@/lib/types";
import { ConfirmDeleteDialog } from "./delete-task";

export function TaskDialog({
  task,
  open,
  onOpenChange,
}: {
  task: Task;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const updateTask = useBoardStore((s) => s.updateTask);
  const columnOf = useBoardStore((s) => s.columnOf);
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [minutesInput, setMinutesInput] = useState("");
  const [loggingTime, setLoggingTime] = useState(false);

  const columnId = columnOf(task.id);
  const columnTitle = COLUMNS.find((c) => c.id === columnId)?.title;

  function startEditing() {
    setTitle(task.title);
    setDescription(task.description ?? "");
    setEditing(true);
  }

  function save() {
    const trimmed = title.trim();
    if (!trimmed) return;
    updateTask(task.id, {
      title: trimmed,
      description: description.trim() || undefined,
    });
    setEditing(false);
  }

  async function logTime() {
    const minutes = Math.round(Number(minutesInput));
    if (!Number.isFinite(minutes) || minutes < 1) return;
    setLoggingTime(true);
    try {
      await logWorkBlock({ taskId: task.id, minutes });
      toast.success(`Logged ${minutes} min`, { description: task.title });
      setMinutesInput("");
    } catch (error) {
      console.error("Could not log work block:", error);
      toast.error("Couldn't log time", { description: "Try again." });
    } finally {
      setLoggingTime(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setEditing(false);
      }}
    >
      <DialogContent>
        {editing ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <DialogHeader>
              <DialogTitle>Edit task</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="task-title"
                className="text-xs font-medium text-muted-foreground"
              >
                Title
              </label>
              <Input
                id="task-title"
                autoFocus
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="task-description"
                className="text-xs font-medium text-muted-foreground"
              >
                Description
              </label>
              <Textarea
                id="task-description"
                value={description}
                placeholder="Add a description…"
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditing(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!title.trim()}>
                Save
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="pr-24 leading-snug">
                {task.title}
              </DialogTitle>
            </DialogHeader>
            {columnTitle && (
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  Status
                </span>
                <Badge variant="secondary" className="rounded-full">
                  {columnTitle}
                </Badge>
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                Description
              </span>
              {task.description ? (
                <p className="text-sm whitespace-pre-wrap leading-relaxed">
                  {task.description}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No description
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="log-minutes"
                className="text-xs font-medium text-muted-foreground"
              >
                Log time
              </label>
              <form
                className="flex items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  logTime();
                }}
              >
                <Input
                  id="log-minutes"
                  type="number"
                  min={1}
                  step={1}
                  inputMode="numeric"
                  placeholder="Minutes"
                  value={minutesInput}
                  onChange={(e) => setMinutesInput(e.target.value)}
                  className="w-24"
                />
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={loggingTime || !minutesInput}
                >
                  Add
                </Button>
              </form>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              className="absolute top-2 right-10"
              onClick={startEditing}
            >
              <Pencil />
              <span className="sr-only">Edit task</span>
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="absolute top-2 right-18 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 />
              <span className="sr-only">Delete task</span>
            </Button>
          </>
        )}
      </DialogContent>
      <ConfirmDeleteDialog
        task={task}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        onConfirm={() => onOpenChange(false)}
      />
    </Dialog>
  );
}
