"use client";

import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { Badge } from "@/components/ui/badge";
import { SortableTaskCard } from "./task-card";
import { AddTask } from "./add-task";
import type { ColumnId, Task } from "@/lib/types";

export function Column({
  id,
  title,
  tasks,
}: {
  id: ColumnId;
  title: string;
  tasks: Task[];
}) {
  const { setNodeRef } = useDroppable({ id });

  return (
    <div className="bg-muted/50 flex w-72 shrink-0 flex-col gap-2 rounded-lg p-2">
      <div className="flex items-center gap-2 px-1 py-1">
        <h2 className="text-sm font-semibold">{title}</h2>
        <Badge variant="secondary">{tasks.length}</Badge>
      </div>
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <div ref={setNodeRef} className="flex min-h-16 flex-1 flex-col gap-2">
          {tasks.map((task) => (
            <SortableTaskCard key={task.id} task={task} />
          ))}
        </div>
      </SortableContext>
      <AddTask columnId={id} />
    </div>
  );
}
