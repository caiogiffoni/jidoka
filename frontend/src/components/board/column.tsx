"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { SortableTaskCard } from "./task-card";
import { AddTask } from "./add-task";
import type { ColumnId, Task } from "@/lib/types";

const ACCENTS: Record<
  ColumnId,
  { dot: string; surface: string; badge: string; title: string }
> = {
  todo: {
    dot: "bg-sky-500",
    surface:
      "border-sky-500/60 bg-sky-500/20 dark:border-sky-400/45 dark:bg-sky-400/20",
    badge: "bg-sky-500/30 text-sky-900 dark:text-sky-100",
    title: "text-sky-950 dark:text-sky-50",
  },
  in_progress: {
    dot: "bg-amber-500",
    surface:
      "border-amber-500/60 bg-amber-500/20 dark:border-amber-400/45 dark:bg-amber-400/20",
    badge: "bg-amber-500/30 text-amber-900 dark:text-amber-100",
    title: "text-amber-950 dark:text-amber-50",
  },
  done: {
    dot: "bg-emerald-500",
    surface:
      "border-emerald-500/60 bg-emerald-500/20 dark:border-emerald-400/45 dark:bg-emerald-400/20",
    badge: "bg-emerald-500/30 text-emerald-900 dark:text-emerald-100",
    title: "text-emerald-950 dark:text-emerald-50",
  },
};

export function Column({
  id,
  title,
  tasks,
}: {
  id: ColumnId;
  title: string;
  tasks: Task[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      className={cn(
        "flex max-h-[calc(100dvh-7.5rem)] w-72 shrink-0 flex-col gap-2 rounded-xl border p-2 shadow-xs transition-colors",
        ACCENTS[id].surface,
        isOver && "border-ring/50 shadow-md",
      )}
    >
      <div className="flex items-center gap-2 px-1.5 pt-1">
        <span className={cn("size-2 rounded-full", ACCENTS[id].dot)} />
        <h2
          className={cn(
            "text-sm font-semibold tracking-tight",
            ACCENTS[id].title,
          )}
        >
          {title}
        </h2>
        <Badge
          className={cn(
            "ml-auto rounded-full border-transparent px-2 font-mono text-[11px] tabular-nums",
            ACCENTS[id].badge,
          )}
        >
          {tasks.length}
        </Badge>
      </div>
      <SortableContext
        items={tasks.map((t) => t.id)}
        strategy={verticalListSortingStrategy}
      >
        <div
          ref={setNodeRef}
          className="flex min-h-16 flex-1 flex-col gap-2 overflow-y-auto rounded-md"
        >
          {tasks.length === 0 && (
            <div className="rounded-lg border border-dashed border-muted-foreground/25 py-6 text-center text-xs text-muted-foreground">
              Drop tasks here
            </div>
          )}
          {tasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} />
          ))}
        </div>
      </SortableContext>
      <AddTask columnId={id} />
    </div>
  );
}
