"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { cn } from "@/lib/utils";
import { SortableTaskCard } from "./task-card";
import { AddTask } from "./add-task";
import type { ColumnId, Project, Task } from "@/lib/types";

// The andon light, reduced to its minimum: station color lives only in the
// status dot. Everything else on the column is neutral.
const DOTS: Record<ColumnId, string> = {
  todo: "bg-sky-500",
  in_progress: "bg-amber-500",
  done: "bg-emerald-500",
};

export function Column({
  id,
  title,
  tasks,
  projects,
}: {
  id: ColumnId;
  title: string;
  tasks: Task[];
  projects: Project[];
}) {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      className={cn(
        "flex max-h-[calc(100dvh-7.5rem)] w-72 shrink-0 flex-col gap-2 rounded-xl bg-muted/50 p-2 transition-shadow duration-150 dark:bg-muted/30",
        isOver && "ring-1 ring-ring/50",
      )}
    >
      <div className="flex items-center gap-2 px-1.5 pt-1">
        <span className={cn("size-1.5 rounded-full", DOTS[id])} />
        <h2 className="text-sm font-medium tracking-tight">{title}</h2>
        <span className="ml-auto pr-1 font-mono text-[11px] tabular-nums text-muted-foreground">
          {tasks.length}
        </span>
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
            <div className="rounded-lg border border-dashed py-6 text-center text-xs text-muted-foreground">
              Drop tasks here
            </div>
          )}
          {tasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} projects={projects} />
          ))}
        </div>
      </SortableContext>
      <AddTask columnId={id} />
    </div>
  );
}
