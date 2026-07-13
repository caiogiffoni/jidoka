"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useBoardStore } from "@/stores/board-store";
import { COLUMNS, type ColumnId } from "@/lib/types";
import { cn } from "@/lib/utils";
import { createTask } from "@/app/actions";

export function AddTaskDialog() {
  const addTask = useBoardStore((s) => s.addTask);
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [columnId, setColumnId] = useState<ColumnId>("todo");

  function reset() {
    setTitle("");
    setDescription("");
    setColumnId("todo");
  }

  async function submit() {
    const trimmed = title.trim();
    if (!trimmed || pending) return;
    setPending(true);
    try {
      const task = await createTask({
        columnId,
        title: trimmed,
        description: description.trim() || undefined,
      });
      addTask(columnId, task);
      reset();
      setOpen(false);
    } catch (error) {
      console.error("Could not create task:", error);
      toast.error("Couldn't create task", {
        description: "Nothing was saved. Check the connection and try again.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus /> Add task
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add task</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="new-task-title"
              className="text-xs font-medium text-muted-foreground"
            >
              Title
            </label>
            <Input
              id="new-task-title"
              autoFocus
              value={title}
              placeholder="Task title…"
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="new-task-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description <span className="font-normal">(optional)</span>
            </label>
            <Textarea
              id="new-task-description"
              value={description}
              placeholder="Add a description…"
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span
              id="new-task-column-label"
              className="text-xs font-medium text-muted-foreground"
            >
              Column
            </span>
            <div
              role="group"
              aria-labelledby="new-task-column-label"
              className="flex gap-1.5"
            >
              {COLUMNS.map((column) => (
                <Button
                  key={column.id}
                  type="button"
                  variant={columnId === column.id ? "secondary" : "ghost"}
                  size="sm"
                  aria-pressed={columnId === column.id}
                  className={cn(
                    "flex-1",
                    columnId === column.id && "ring-1 ring-ring/40",
                  )}
                  onClick={() => setColumnId(column.id)}
                >
                  {column.title}
                </Button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!title.trim() || pending}>
              {pending ? "Adding…" : "Add task"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
