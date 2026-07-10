"use client";

import { useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragOverEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { useBoardStore } from "@/stores/board-store";
import { COLUMNS, isColumnId, type ColumnId, type Task } from "@/lib/types";
import { Column } from "./column";
import { TaskCard } from "./task-card";

export function Board() {
  const { tasks, columnOf, moveTaskToColumn, reorderTask } = useBoardStore();
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  function resolveColumn(id: string | number): ColumnId | undefined {
    return isColumnId(id) ? id : columnOf(String(id));
  }

  function handleDragStart({ active }: DragStartEvent) {
    const column = columnOf(String(active.id));
    setActiveTask(
      column ? (tasks[column].find((t) => t.id === active.id) ?? null) : null,
    );
  }

  function handleDragOver({ active, over }: DragOverEvent) {
    if (!over) return;
    const fromColumn = columnOf(String(active.id));
    const toColumn = resolveColumn(over.id);
    if (!fromColumn || !toColumn || fromColumn === toColumn) return;
    // Crossing into another column mid-drag: move the task there so the
    // sortable list previews the drop position.
    moveTaskToColumn(
      String(active.id),
      toColumn,
      isColumnId(over.id) ? undefined : String(over.id),
    );
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    setActiveTask(null);
    if (!over || active.id === over.id) return;
    const column = columnOf(String(active.id));
    const overColumn = resolveColumn(over.id);
    if (column && column === overColumn && !isColumnId(over.id)) {
      reorderTask(column, String(active.id), String(over.id));
    }
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragOver={handleDragOver}
      onDragEnd={handleDragEnd}
      onDragCancel={() => setActiveTask(null)}
    >
      <div className="flex gap-4 overflow-x-auto p-4">
        {COLUMNS.map((column) => (
          <Column
            key={column.id}
            id={column.id}
            title={column.title}
            tasks={tasks[column.id]}
          />
        ))}
      </div>
      <DragOverlay>
        {activeTask && <TaskCard task={activeTask} overlay />}
      </DragOverlay>
    </DndContext>
  );
}
