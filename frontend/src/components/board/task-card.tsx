"use client";

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Task } from "@/lib/types";

export function TaskCard({ task, overlay }: { task: Task; overlay?: boolean }) {
  return (
    <Card
      className={cn(
        "cursor-grab gap-0 border-border/60 py-3 shadow-xs transition-[border-color,box-shadow] duration-150 select-none hover:border-ring/40 hover:shadow-md",
        overlay &&
          "cursor-grabbing rotate-2 border-ring/50 shadow-xl ring-1 ring-ring/20",
      )}
    >
      <CardContent className="px-3">
        <p className="text-sm leading-snug font-medium">{task.title}</p>
        {task.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {task.description}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function SortableTaskCard({ task }: { task: Task }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        isDragging &&
          "rounded-xl border border-dashed border-muted-foreground/30 bg-muted/60 *:invisible",
      )}
      {...attributes}
      {...listeners}
    >
      <TaskCard task={task} />
    </div>
  );
}
