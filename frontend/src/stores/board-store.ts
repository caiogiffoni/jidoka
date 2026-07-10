import { create } from "zustand";
import { arrayMove } from "@dnd-kit/sortable";
import type { ColumnId, Task } from "@/lib/types";

// Array order within a column is the display order; the future backend
// persists it as an `order` field per task.
type TasksByColumn = Record<ColumnId, Task[]>;

const seedTasks: TasksByColumn = {
  todo: [
    {
      id: "seed-4",
      title: "FastAPI backend skeleton",
      description:
        "Scaffold the FastAPI app with docker-compose, Postgres + pgvector, and a health endpoint.",
    },
    { id: "seed-5", title: "LangGraph agent loop" },
    {
      id: "seed-6",
      title: "HITL approval flow",
      description:
        "Propose → approve → apply diff flow using interrupt(); the agent never writes to the board directly.",
    },
  ],
  in_progress: [
    { id: "seed-2", title: "Build kanban board UI" },
    { id: "seed-3", title: "Wire drag and drop" },
  ],
  done: [{ id: "seed-1", title: "Scaffold Next.js frontend" }],
};

interface BoardState {
  tasks: TasksByColumn;
  columnOf: (taskId: string) => ColumnId | undefined;
  addTask: (columnId: ColumnId, title: string, description?: string) => void;
  moveTaskToColumn: (
    taskId: string,
    toColumn: ColumnId,
    beforeTaskId?: string,
  ) => void;
  reorderTask: (columnId: ColumnId, activeId: string, overId: string) => void;
}

export const useBoardStore = create<BoardState>((set, get) => ({
  tasks: seedTasks,

  columnOf: (taskId) => {
    const { tasks } = get();
    return (Object.keys(tasks) as ColumnId[]).find((col) =>
      tasks[col].some((t) => t.id === taskId),
    );
  },

  addTask: (columnId, title, description) =>
    set((state) => ({
      tasks: {
        ...state.tasks,
        [columnId]: [
          ...state.tasks[columnId],
          { id: crypto.randomUUID(), title, description },
        ],
      },
    })),

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
