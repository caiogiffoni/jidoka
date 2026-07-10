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
        "cursor-grab py-3 shadow-sm",
        overlay && "cursor-grabbing shadow-lg",
      )}
    >
      <CardContent className="px-3">
        <p className="text-sm font-medium">{task.title}</p>
        {task.description && (
          <p className="text-muted-foreground mt-1 line-clamp-2 text-xs">
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
      className={cn(isDragging && "opacity-40")}
      {...attributes}
      {...listeners}
    >
      <TaskCard task={task} />
    </div>
  );
}
