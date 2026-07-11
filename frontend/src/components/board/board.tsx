"use client";

import { useRef, useState } from "react";
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
import {
  COLUMNS,
  isColumnId,
  type ColumnId,
  type Task,
  type TasksByColumn,
} from "@/lib/types";
import { Column } from "./column";
import { TaskCard } from "./task-card";
import { moveTask } from "@/app/actions";

export function Board({ initialTasks }: { initialTasks: TasksByColumn }) {
  // Hydrate the store from the server-fetched board exactly once, before the
  // first subscription read, so SSR and the first client render agree. After
  // that the store owns board state; mutations update it optimistically.
  const hydrated = useRef<boolean | null>(null);
  if (hydrated.current == null) {
    hydrated.current = true;
    useBoardStore.setState({ tasks: initialTasks });
  }

  const { tasks, columnOf, moveTaskToColumn, reorderTask } = useBoardStore();
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const dragOrigin = useRef<{ column: ColumnId; index: number } | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
  );

  function resolveColumn(id: string | number): ColumnId | undefined {
    return isColumnId(id) ? id : columnOf(String(id));
  }

  function handleDragStart({ active }: DragStartEvent) {
    const column = columnOf(String(active.id));
    dragOrigin.current = column
      ? { column, index: tasks[column].findIndex((t) => t.id === active.id) }
      : null;
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
    const origin = dragOrigin.current;
    dragOrigin.current = null;

    const taskId = String(active.id);
    if (over && active.id !== over.id) {
      const column = columnOf(taskId);
      const overColumn = resolveColumn(over.id);
      if (column && column === overColumn && !isColumnId(over.id)) {
        reorderTask(column, taskId, String(over.id));
      }
    }

    // Persist the final placement if it changed. The store is already
    // updated (optimistically), so this is fire-and-forget.
    if (!origin) return;
    const state = useBoardStore.getState();
    const finalColumn = state.columnOf(taskId);
    if (!finalColumn) return;
    const finalIndex = state.tasks[finalColumn].findIndex(
      (t) => t.id === taskId,
    );
    if (finalColumn === origin.column && finalIndex === origin.index) return;
    moveTask({ taskId, columnId: finalColumn, position: finalIndex }).catch(
      (error) => console.error("Could not persist move:", error),
    );
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
      <div className="flex flex-1 items-start gap-4 overflow-x-auto p-4 sm:p-6">
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
