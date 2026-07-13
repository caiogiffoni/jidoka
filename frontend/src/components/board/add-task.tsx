"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBoardStore } from "@/stores/board-store";
import type { ColumnId } from "@/lib/types";
import { createTask } from "@/app/actions";

export function AddTask({ columnId }: { columnId: ColumnId }) {
  const addTask = useBoardStore((s) => s.addTask);
  const [editing, setEditing] = useState(false);
  const [pending, setPending] = useState(false);
  const [title, setTitle] = useState("");

  async function submit() {
    const trimmed = title.trim();
    if (!trimmed) {
      setTitle("");
      setEditing(false);
      return;
    }
    // Enter and the subsequent blur both call submit; only run once.
    if (pending) return;
    setPending(true);
    try {
      const task = await createTask({ columnId, title: trimmed });
      addTask(columnId, task);
      setTitle("");
      setEditing(false);
    } catch (error) {
      console.error("Could not create task:", error);
      toast.error("Couldn't create task", {
        description: "Your title is still here - press Enter to try again.",
      });
    } finally {
      setPending(false);
    }
  }

  if (!editing) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="w-full justify-start text-muted-foreground hover:text-foreground"
        onClick={() => setEditing(true)}
      >
        <Plus /> Add task
      </Button>
    );
  }

  return (
    <Input
      autoFocus
      value={title}
      placeholder="Task title…"
      aria-label="Task title"
      disabled={pending}
      onChange={(e) => setTitle(e.target.value)}
      onBlur={submit}
      onKeyDown={(e) => {
        if (e.key === "Enter") submit();
        if (e.key === "Escape") {
          setTitle("");
          setEditing(false);
        }
      }}
    />
  );
}
