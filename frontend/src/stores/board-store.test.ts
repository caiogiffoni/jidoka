import { beforeEach, describe, expect, it } from "vitest";
import { useBoardStore } from "./board-store";
import type { Task } from "@/lib/types";

function task(id: string, overrides: Partial<Task> = {}): Task {
  return { id, title: `Task ${id}`, ...overrides };
}

beforeEach(() => {
  useBoardStore.setState({ tasks: { todo: [], in_progress: [], done: [] } });
});

describe("addTask", () => {
  it("appends to the target column", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("todo", task("b"));
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "a",
      "b",
    ]);
  });
});

describe("columnOf", () => {
  it("finds the column containing a task", () => {
    useBoardStore.getState().addTask("in_progress", task("a"));
    expect(useBoardStore.getState().columnOf("a")).toBe("in_progress");
  });

  it("returns undefined for an unknown task", () => {
    expect(useBoardStore.getState().columnOf("missing")).toBeUndefined();
  });
});

describe("updateTask", () => {
  it("merges title/description onto the matching task", () => {
    useBoardStore.getState().addTask("todo", task("a", { title: "Old" }));
    useBoardStore
      .getState()
      .updateTask("a", { title: "New", description: "d" });
    expect(useBoardStore.getState().tasks.todo[0]).toMatchObject({
      title: "New",
      description: "d",
    });
  });

  it("is a no-op for an unknown task", () => {
    const before = useBoardStore.getState().tasks;
    useBoardStore.getState().updateTask("missing", { title: "x" });
    expect(useBoardStore.getState().tasks).toBe(before);
  });
});

describe("moveTaskToColumn", () => {
  it("moves a task to the end of the target column by default", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("in_progress", task("b"));
    useBoardStore.getState().moveTaskToColumn("a", "in_progress");
    const state = useBoardStore.getState();
    expect(state.tasks.todo).toHaveLength(0);
    expect(state.tasks.in_progress.map((t) => t.id)).toEqual(["b", "a"]);
  });

  it("inserts before a given task when beforeTaskId is provided", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("in_progress", task("b"));
    useBoardStore.getState().moveTaskToColumn("a", "in_progress", "b");
    expect(
      useBoardStore.getState().tasks.in_progress.map((t) => t.id),
    ).toEqual(["a", "b"]);
  });

  it("is a no-op when the task is already in the target column", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    const before = useBoardStore.getState().tasks;
    useBoardStore.getState().moveTaskToColumn("a", "todo");
    expect(useBoardStore.getState().tasks).toBe(before);
  });
});

describe("placeTask", () => {
  it("places a task at an exact column + index (rolling back a rejected move)", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("todo", task("b"));
    useBoardStore.getState().moveTaskToColumn("a", "in_progress");

    useBoardStore.getState().placeTask("a", "todo", 0);

    const state = useBoardStore.getState();
    expect(state.tasks.todo.map((t) => t.id)).toEqual(["a", "b"]);
    expect(state.tasks.in_progress).toHaveLength(0);
  });
});

describe("removeTask / restoreTask", () => {
  it("removes a task, then restores it at the same column + index", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("todo", task("b"));
    const removed = task("a");

    useBoardStore.getState().removeTask("a");
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "b",
    ]);

    useBoardStore.getState().restoreTask(removed, "todo", 0);
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "a",
      "b",
    ]);
  });
});

describe("reorderTask", () => {
  it("reorders within a column", () => {
    useBoardStore.getState().addTask("todo", task("a"));
    useBoardStore.getState().addTask("todo", task("b"));
    useBoardStore.getState().addTask("todo", task("c"));
    useBoardStore.getState().reorderTask("todo", "a", "c");
    expect(useBoardStore.getState().tasks.todo.map((t) => t.id)).toEqual([
      "b",
      "c",
      "a",
    ]);
  });
});
