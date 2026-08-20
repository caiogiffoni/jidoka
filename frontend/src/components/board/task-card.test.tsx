import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskCard, SortableTaskCard } from "./task-card";
import { useBoardStore } from "@/stores/board-store";
import type { Task, Project } from "@/lib/types";

vi.mock("@dnd-kit/sortable", () => ({
  useSortable: vi.fn(() => ({
    attributes: {},
    listeners: { onKeyDown: vi.fn() },
    setNodeRef: vi.fn(),
    transform: null,
    transition: undefined,
    isDragging: false,
  })),
}));

vi.mock("@dnd-kit/utilities", () => ({
  CSS: { Transform: { toString: vi.fn(() => "") } },
}));

vi.mock("@/app/actions", () => ({
  archiveTask: vi.fn().mockResolvedValue(undefined),
  deleteTask: vi.fn().mockResolvedValue(undefined),
  fetchTaskMinutes: vi.fn().mockResolvedValue(0),
  updateTask: vi.fn().mockResolvedValue(undefined),
  logWorkBlock: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

vi.mock("./task-dialog", () => ({
  TaskDialog: () => <div data-testid="task-dialog" />,
}));

const task: Task = {
  id: "task-1",
  title: "Test task",
  checklist: [],
};

const projects: Project[] = [];

function setupBoard(tasks: Partial<Record<import("@/lib/types").ColumnId, Task[]>>) {
  useBoardStore.setState({
    tasks: {
      backlog: tasks.backlog ?? [],
      todo: tasks.todo ?? [],
      in_progress: tasks.in_progress ?? [],
      done: tasks.done ?? [],
    },
  });
}

describe("TaskCard", () => {
  it("renders the actions menu with archive and delete items", async () => {
    const user = userEvent.setup();
    const onArchive = vi.fn();
    const onDelete = vi.fn();

    render(
      <TaskCard
        task={task}
        columnId="todo"
        onArchive={onArchive}
        onDelete={onDelete}
      />,
    );

    await user.click(screen.getByRole("button", { name: /task actions/i }));

    expect(screen.getByRole("menuitem", { name: /archive/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /delete/i })).toBeInTheDocument();
  });

  it("calls onArchive and onDelete when the menu items are clicked", async () => {
    const user = userEvent.setup();
    const onArchive = vi.fn();
    const onDelete = vi.fn();

    render(
      <TaskCard
        task={task}
        columnId="todo"
        onArchive={onArchive}
        onDelete={onDelete}
      />,
    );

    await user.click(screen.getByRole("button", { name: /task actions/i }));
    await user.click(screen.getByRole("menuitem", { name: /archive/i }));
    expect(onArchive).toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /task actions/i }));
    await user.click(screen.getByRole("menuitem", { name: /delete/i }));
    expect(onDelete).toHaveBeenCalled();
  });
});

describe("SortableTaskCard", () => {
  beforeEach(() => {
    setupBoard({ todo: [task] });
  });

  it("archives immediately without a confirmation dialog", async () => {
    const user = userEvent.setup();
    render(<SortableTaskCard task={task} columnId="todo" projects={projects} />);

    await user.click(screen.getByRole("button", { name: /task actions/i }));
    await user.click(screen.getByRole("menuitem", { name: /archive/i }));

    expect(screen.queryByRole("dialog", { name: /archive task/i })).not.toBeInTheDocument();
    expect(useBoardStore.getState().tasks.todo).toHaveLength(0);
  });

  it("opens the delete confirmation dialog when delete is selected", async () => {
    const user = userEvent.setup();
    render(<SortableTaskCard task={task} columnId="todo" projects={projects} />);

    await user.click(screen.getByRole("button", { name: /task actions/i }));
    await user.click(screen.getByRole("menuitem", { name: /delete/i }));

    expect(screen.getByRole("dialog", { name: /delete task/i })).toBeInTheDocument();
  });
});
