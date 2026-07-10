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
        "Scaffold the FastAPI app with docker-compose, Postgres + pgvector, and a health endpoint. FastAPI is the single writer to Postgres — Server Actions proxy mutations to it.",
    },
    {
      id: "seed-5",
      title: "LangGraph agent loop",
      description:
        "Explicit StateGraph with agent → tools loop and one tool (create_task) fully wired: chat → tool call → DB → board update. Checkpointed per board via thread_id.",
    },
    {
      id: "seed-6",
      title: "HITL approval flow",
      description:
        "Propose → approve → apply diff flow using interrupt(); the agent never writes to the board directly. Tools accumulate proposed_changes; only the apply node touches the DB.",
    },
  ],
  in_progress: [
    {
      id: "seed-2",
      title: "Build kanban board UI",
      description:
        "Three-column board (To Do / In Progress / Done) with shadcn/ui cards, add-task flows, and a task detail dialog with inline editing.",
    },
    {
      id: "seed-3",
      title: "Wire drag and drop",
      description:
        "dnd-kit sortable cards: reorder within a column and move across columns with a drop preview. Array order is the display order.",
    },
  ],
  done: [
    {
      id: "seed-1",
      title: "Scaffold Next.js frontend",
      description:
        "Next.js App Router + TypeScript + Tailwind v4 + shadcn/ui, with Zustand for ephemeral board state and dark mode via next-themes.",
    },
  ],
};

interface BoardState {
  tasks: TasksByColumn;
  columnOf: (taskId: string) => ColumnId | undefined;
  addTask: (columnId: ColumnId, title: string, description?: string) => void;
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
