import { beforeEach, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import type { ComponentProps, ReactNode } from "react";
import type { DndContext as DndContextType } from "@dnd-kit/core";

type DndProps = ComponentProps<typeof DndContextType>;
let dnd: DndProps;

// Capture the DndContext handlers so tests can drive a drag directly;
// jsdom has no layout, so real pointer/keyboard drags can't be simulated.
vi.mock("@dnd-kit/core", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@dnd-kit/core")>();
  return {
    ...actual,
    DndContext: (props: DndProps & { children?: ReactNode }) => {
      dnd = props;
      return <>{props.children}</>;
    },
    DragOverlay: () => null,
  };
});

vi.mock("./column", () => ({
  Column: ({ id, tasks }: { id: string; tasks: { title: string }[] }) => (
    <ul data-testid={`column-${id}`}>
      {tasks.map((t) => (
        <li key={t.title}>{t.title}</li>
      ))}
    </ul>
  ),
}));

vi.mock("@/app/actions", () => ({
  moveTask: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn() }),
}));

import { Board } from "./board";
import { useBoardStore } from "@/stores/board-store";
import type { Task, TasksByColumn } from "@/lib/types";

function task(id: string): Task {
  return { id, title: `Task ${id}`, checklist: [] };
}

function board(overrides: Partial<TasksByColumn> = {}): TasksByColumn {
  return { backlog: [], todo: [], in_progress: [], done: [], ...overrides };
}

function titlesIn(column: string): string[] {
  return within(screen.getByTestId(`column-${column}`))
    .queryAllByRole("listitem")
    .map((li) => li.textContent ?? "");
}

beforeEach(() => {
  useBoardStore.setState({ tasks: board(), pendingRemovals: new Set() });
});

it("renders new server data when initialTasks changes", () => {
  const { rerender } = render(
    <Board initialTasks={board({ todo: [task("a")] })} projects={[]} />,
  );
  expect(titlesIn("todo")).toEqual(["Task a"]);

  rerender(
    <Board
      initialTasks={board({ todo: [task("a"), task("b")] })}
      projects={[]}
    />,
  );
  expect(titlesIn("todo")).toEqual(["Task a", "Task b"]);
});

it("defers a resync until an active drag ends", () => {
  const { rerender } = render(
    <Board initialTasks={board({ todo: [task("a")] })} projects={[]} />,
  );

  act(() => dnd.onDragStart?.({ active: { id: "a" } } as never));
  rerender(
    <Board
      initialTasks={board({ todo: [task("a"), task("b")] })}
      projects={[]}
    />,
  );
  expect(titlesIn("todo")).toEqual(["Task a"]);

  act(() => dnd.onDragCancel?.({ active: { id: "a" } } as never));
  expect(titlesIn("todo")).toEqual(["Task a", "Task b"]);
});

it("doesn't resurrect a task whose removal is still pending", () => {
  const { rerender } = render(
    <Board initialTasks={board({ todo: [task("a")] })} projects={[]} />,
  );
  act(() => {
    useBoardStore.getState().removeTask("a");
    useBoardStore.getState().markPendingRemoval("a");
  });

  rerender(
    <Board
      initialTasks={board({ todo: [task("a"), task("b")] })}
      projects={[]}
    />,
  );
  expect(titlesIn("todo")).toEqual(["Task b"]);
});

it("restores the origin column and position when a drag is cancelled", () => {
  render(
    <Board
      initialTasks={board({ todo: [task("a"), task("b")], done: [task("c")] })}
      projects={[]}
    />,
  );

  act(() => dnd.onDragStart?.({ active: { id: "a" } } as never));
  act(() =>
    dnd.onDragOver?.({ active: { id: "a" }, over: { id: "done" } } as never),
  );
  expect(titlesIn("done")).toEqual(["Task c", "Task a"]);

  act(() => dnd.onDragCancel?.({ active: { id: "a" } } as never));
  expect(titlesIn("todo")).toEqual(["Task a", "Task b"]);
  expect(titlesIn("done")).toEqual(["Task c"]);
});
