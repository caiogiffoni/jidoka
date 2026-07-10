"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useBoardStore } from "@/stores/board-store";
import type { ColumnId } from "@/lib/types";

export function AddTask({ columnId }: { columnId: ColumnId }) {
  const addTask = useBoardStore((s) => s.addTask);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");

  function submit() {
    const trimmed = title.trim();
    if (trimmed) addTask(columnId, trimmed);
    setTitle("");
    setEditing(false);
  }

  if (!editing) {
    return (
      <Button
        variant="ghost"
        size="sm"
        className="text-muted-foreground w-full justify-start"
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
