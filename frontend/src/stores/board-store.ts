import { create } from "zustand";
import { arrayMove } from "@dnd-kit/sortable";
import type { ColumnId, Task, TasksByColumn } from "@/lib/types";

const emptyBoard: TasksByColumn = { todo: [], in_progress: [], done: [] };

interface BoardState {
  tasks: TasksByColumn;
  columnOf: (taskId: string) => ColumnId | undefined;
  setTasks: (tasks: TasksByColumn) => void;
  addTask: (columnId: ColumnId, task: Task) => void;
  updateTask: (
    taskId: string,
    updates: Pick<Task, "title" | "description">,
  ) => void;
  moveTaskToColumn: (
    taskId: string,
    toColumn: ColumnId,
    beforeTaskId?: string,
  ) => void;
  reorderTask: (columnId: ColumnId, activeId: string, overId: string) => void;
  placeTask: (taskId: string, columnId: ColumnId, index: number) => void;
}

export const useBoardStore = create<BoardState>((set, get) => ({
  tasks: emptyBoard,

  columnOf: (taskId) => {
    const { tasks } = get();
    return (Object.keys(tasks) as ColumnId[]).find((col) =>
      tasks[col].some((t) => t.id === taskId),
    );
  },

  setTasks: (tasks) => set({ tasks }),

  addTask: (columnId, task) =>
    set((state) => ({
      tasks: {
        ...state.tasks,
        [columnId]: [...state.tasks[columnId], task],
      },
    })),

  updateTask: (taskId, updates) =>
    set((state) => {
      const column = get().columnOf(taskId);
      if (!column) return state;
      return {
        tasks: {
          ...state.tasks,
          [column]: state.tasks[column].map((t) =>
            t.id === taskId ? { ...t, ...updates } : t,
          ),
        },
      };
    }),

  moveTaskToColumn: (taskId, toColumn, beforeTaskId) =>
    set((state) => {
      const fromColumn = get().columnOf(taskId);
      if (!fromColumn || fromColumn === toColumn) return state;

      const task = state.tasks[fromColumn].find((t) => t.id === taskId);
      if (!task) return state;

      const target = [...state.tasks[toColumn]];
      const insertAt = beforeTaskId
        ? target.findIndex((t) => t.id === beforeTaskId)
        : target.length;
      target.splice(insertAt === -1 ? target.length : insertAt, 0, task);

      return {
        tasks: {
          ...state.tasks,
          [fromColumn]: state.tasks[fromColumn].filter(
            (t) => t.id !== taskId,
          ),
          [toColumn]: target,
        },
      };
    }),

  // Put a task at an exact column + index, e.g. rolling back an optimistic
  // move the server rejected.
  placeTask: (taskId, columnId, index) =>
    set((state) => {
      const fromColumn = get().columnOf(taskId);
      if (!fromColumn) return state;
      const task = state.tasks[fromColumn].find((t) => t.id === taskId);
      if (!task) return state;

      const without = state.tasks[fromColumn].filter((t) => t.id !== taskId);
      const target =
        fromColumn === columnId ? [...without] : [...state.tasks[columnId]];
      target.splice(Math.min(index, target.length), 0, task);

      return {
        tasks: {
          ...state.tasks,
          [fromColumn]: fromColumn === columnId ? target : without,
          [columnId]: target,
        },
      };
    }),

  reorderTask: (columnId, activeId, overId) =>
    set((state) => {
      const column = state.tasks[columnId];
      const from = column.findIndex((t) => t.id === activeId);
      const to = column.findIndex((t) => t.id === overId);
      if (from === -1 || to === -1) return state;
      return {
        tasks: { ...state.tasks, [columnId]: arrayMove(column, from, to) },
      };
    }),
}));
