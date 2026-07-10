"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
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

export function AddTaskDialog() {
  const addTask = useBoardStore((s) => s.addTask);
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [columnId, setColumnId] = useState<ColumnId>("todo");

  function reset() {
    setTitle("");
    setDescription("");
    setColumnId("todo");
  }

  function submit() {
    const trimmed = title.trim();
    if (!trimmed) return;
    addTask(columnId, trimmed, description.trim() || undefined);
    reset();
    setOpen(false);
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
          <Input
            autoFocus
            value={title}
            placeholder="Task title…"
            onChange={(e) => setTitle(e.target.value)}
          />
          <Textarea
            value={description}
            placeholder="Description (optional)…"
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="flex gap-1.5">
            {COLUMNS.map((column) => (
              <Button
                key={column.id}
                type="button"
                variant={columnId === column.id ? "secondary" : "ghost"}
                size="sm"
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
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!title.trim()}>
              Add task
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
