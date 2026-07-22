import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/app/actions", () => ({
  recordWorkBlock: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { recordWorkBlock } from "@/app/actions";
import { DEFAULT_SETTINGS, usePomodoroStore } from "./pomodoro-store";

const initialState = usePomodoroStore.getState();

beforeEach(() => {
  usePomodoroStore.setState(initialState, true);
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-01-01T10:00:00.000Z"));
  vi.mocked(recordWorkBlock).mockClear();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("start / pause / resume / stop", () => {
  it("starting sets endsAt to now + the phase duration", () => {
    usePomodoroStore.getState().start();
    const state = usePomodoroStore.getState();
    expect(state.status).toBe("running");
    expect(state.endsAt).toBe(Date.now() + DEFAULT_SETTINGS.workMin * 60_000);
  });

  it("pause captures the remaining time and clears endsAt", () => {
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(60_000);
    usePomodoroStore.getState().pause();
    const state = usePomodoroStore.getState();
    expect(state.status).toBe("paused");
    expect(state.endsAt).toBeNull();
    expect(state.remainingMs).toBe(DEFAULT_SETTINGS.workMin * 60_000 - 60_000);
  });

  it("resume recomputes endsAt from the remaining time", () => {
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(60_000);
    usePomodoroStore.getState().pause();
    vi.advanceTimersByTime(30_000); // time passes while paused - shouldn't count
    usePomodoroStore.getState().resume();
    const state = usePomodoroStore.getState();
    expect(state.status).toBe("running");
    expect(state.remainingMs).toBeNull();
    expect(state.endsAt).toBe(
      Date.now() + (DEFAULT_SETTINGS.workMin * 60_000 - 60_000),
    );
  });

  it("stop returns to idle without persisting anything", () => {
    usePomodoroStore.getState().setTask("task-1");
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().stop();
    const state = usePomodoroStore.getState();
    expect(state.status).toBe("idle");
    expect(state.phase).toBe("focus");
    expect(recordWorkBlock).not.toHaveBeenCalled();
  });
});

describe("finishPhase", () => {
  it("persists a focus block for the linked task and starts the break", () => {
    usePomodoroStore.getState().setTask("task-1");
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().finishPhase();

    expect(recordWorkBlock).toHaveBeenCalledWith({
      taskId: "task-1",
      startedAt: expect.any(Number),
      endedAt: expect.any(Number),
    });
    const state = usePomodoroStore.getState();
    expect(state.phase).toBe("break");
    expect(state.status).toBe("running"); // autoStartBreak defaults to true
    expect(state.doneToday).toBe(1);
    expect(state.alarm).not.toBeNull();
  });

  it("does not persist anything when no task is linked", () => {
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().finishPhase();
    expect(recordWorkBlock).not.toHaveBeenCalled();
  });

  it("a finished break returns to an idle focus phase - work never auto-starts", () => {
    usePomodoroStore.getState().start(); // focus
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().finishPhase(); // -> break, auto-started

    vi.advanceTimersByTime(DEFAULT_SETTINGS.breakMin * 60_000);
    usePomodoroStore.getState().finishPhase(); // break finishes

    const state = usePomodoroStore.getState();
    expect(state.phase).toBe("focus");
    expect(state.status).toBe("idle");
  });

  it("takes a long break every `longBreakEvery` focus blocks", () => {
    usePomodoroStore.getState().updateSettings({ longBreakEvery: 2 });

    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().finishPhase();
    expect(usePomodoroStore.getState().phase).toBe("break");

    vi.advanceTimersByTime(DEFAULT_SETTINGS.breakMin * 60_000);
    usePomodoroStore.getState().finishPhase();
    expect(usePomodoroStore.getState().phase).toBe("focus");

    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000);
    usePomodoroStore.getState().finishPhase();
    expect(usePomodoroStore.getState().phase).toBe("long_break");
  });
});

describe("catchUp", () => {
  it("discards a phase that expired while the page was closed - no persist, no alarm", () => {
    usePomodoroStore.getState().setTask("task-1");
    usePomodoroStore.getState().start();
    vi.advanceTimersByTime(DEFAULT_SETTINGS.workMin * 60_000 + 60_000);

    usePomodoroStore.getState().catchUp();

    const state = usePomodoroStore.getState();
    expect(state.status).toBe("idle");
    expect(state.phase).toBe("focus");
    expect(state.alarm).toBeNull();
    expect(recordWorkBlock).not.toHaveBeenCalled();
  });

  it("is a no-op if the phase hasn't actually expired yet", () => {
    usePomodoroStore.getState().start();
    usePomodoroStore.getState().catchUp();
    expect(usePomodoroStore.getState().status).toBe("running");
  });
});
