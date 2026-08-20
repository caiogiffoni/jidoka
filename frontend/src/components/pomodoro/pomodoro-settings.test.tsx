import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PomodoroSettingsDialog } from "./pomodoro-settings";
import { usePomodoroStore } from "@/stores/pomodoro-store";

vi.mock("@/lib/alarm", () => ({
  ALARM_SOUNDS: [
    { value: "digital", label: "Digital" },
    { value: "bell", label: "Bell" },
  ],
}));

const initialState = usePomodoroStore.getState();

describe("PomodoroSettingsDialog", () => {
  beforeEach(() => {
    localStorage.clear();
    usePomodoroStore.setState(initialState, true);
  });

  afterEach(() => {
    document.title = "Jidoka";
  });

  it("lets the user toggle the tab title timer option", async () => {
    const user = userEvent.setup();
    render(<PomodoroSettingsDialog />);

    await user.click(screen.getByRole("button", { name: "Timer settings" }));

    const checkbox = screen.getByRole("checkbox", {
      name: /show timer in tab title/i,
    });
    expect(checkbox).toBeChecked();

    await user.click(checkbox);
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(usePomodoroStore.getState().settings.showTimerInTabTitle).toBe(
      false,
    );
  });
});
