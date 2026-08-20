import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import { PomodoroMenu } from "./pomodoro-menu";
import { usePomodoroStore } from "@/stores/pomodoro-store";

vi.mock("@/lib/alarm", () => ({
  playAlarm: vi.fn(),
}));

const initialState = usePomodoroStore.getState();

describe("PomodoroMenu tab title", () => {
  beforeEach(() => {
    localStorage.clear();
    usePomodoroStore.setState(initialState, true);
    document.title = "Jidoka";
  });

  afterEach(() => {
    document.title = "Jidoka";
  });

  it("shows the remaining time in the tab title while running", async () => {
    render(<PomodoroMenu />);

    act(() => {
      usePomodoroStore.setState({
        status: "running",
        phase: "focus",
        endsAt: Date.now() + 10 * 60_000 + 5_000,
        remainingMs: null,
      });
    });

    await waitFor(() => {
      expect(document.title).toBe("Jidoka (10:05)");
    });
  });

  it("shows the remaining time in the tab title while paused", async () => {
    render(<PomodoroMenu />);

    act(() => {
      usePomodoroStore.setState({
        status: "paused",
        phase: "focus",
        endsAt: null,
        remainingMs: 3 * 60_000 + 30_000,
      });
    });

    await waitFor(() => {
      expect(document.title).toBe("Jidoka (3:30)");
    });
  });

  it("resets the tab title to Jidoka when idle", async () => {
    render(<PomodoroMenu />);

    act(() => {
      usePomodoroStore.setState({
        status: "running",
        phase: "focus",
        endsAt: Date.now() + 5 * 60_000,
        remainingMs: null,
      });
    });
    await waitFor(() => expect(document.title).toBe("Jidoka (5:00)"));

    act(() => {
      usePomodoroStore.setState({
        status: "idle",
        endsAt: null,
        remainingMs: null,
      });
    });
    await waitFor(() => expect(document.title).toBe("Jidoka"));
  });

  it("keeps the plain title when showTimerInTabTitle is disabled", async () => {
    render(<PomodoroMenu />);

    act(() => {
      usePomodoroStore.setState({
        status: "running",
        phase: "focus",
        endsAt: Date.now() + 7 * 60_000 + 30_000,
        remainingMs: null,
        settings: {
          ...usePomodoroStore.getState().settings,
          showTimerInTabTitle: false,
        },
      });
    });

    await waitFor(() => {
      expect(document.title).toBe("Jidoka");
    });
  });
});
