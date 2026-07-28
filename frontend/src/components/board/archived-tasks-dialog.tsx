"use client";

import { useState } from "react";
import { Archive, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { archiveTask, fetchArchivedTasks } from "@/app/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Task } from "@/lib/types";

export function ArchivedTasksDialog() {
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const archived = await fetchArchivedTasks();
      setTasks(archived);
    } catch (error) {
      console.error("Could not load archived tasks:", error);
      toast.error("Couldn't load archived tasks");
    } finally {
      setLoading(false);
    }
  }

  async function unarchive(task: Task) {
    try {
      await archiveTask(task.id, false);
      setTasks((prev) => prev.filter((t) => t.id !== task.id));
      toast.success("Task restored", { description: task.title });
    } catch (error) {
      console.error("Could not restore task:", error);
      toast.error("Couldn't restore task", { description: "Try again." });
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (next) load();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Archived tasks">
          <Archive />
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Archived tasks</DialogTitle>
        </DialogHeader>
        {loading && tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : tasks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No archived tasks.</p>
        ) : (
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {tasks.map((task) => (
              <li
                key={task.id}
                className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-muted"
              >
                <span className="min-w-0 truncate text-sm">{task.title}</span>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => unarchive(task)}
                  aria-label={`Restore ${task.title}`}
                >
                  <RotateCcw />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </DialogContent>
    </Dialog>
  );
}
