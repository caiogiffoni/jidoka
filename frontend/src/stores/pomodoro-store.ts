import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AlarmSound } from "@/lib/alarm";

export type PomodoroPhase = "focus" | "break" | "long_break";
export type PomodoroStatus = "idle" | "running" | "paused";

export interface PomodoroSettings {
  workMin: number;
  breakMin: number;
  longBreakMin: number;
  longBreakEvery: number;
  volume: number; // 0-100
  alarmSound: AlarmSound;
  repeatAlarmSec: number; // ring again every N seconds until acknowledged
  stopAlarmMin: number; // an unacknowledged alarm gives up after N minutes
  autoStartBreak: boolean;
  dailyGoal: number; // focus blocks per day; 0 = off
}

export const DEFAULT_SETTINGS: PomodoroSettings = {
  workMin: 25,
  breakMin: 5,
  longBreakMin: 15,
  longBreakEvery: 4,
  volume: 100,
  alarmSound: "digital",
  repeatAlarmSec: 5,
  stopAlarmMin: 3,
  autoStartBreak: true,
  dailyGoal: 0,
};

export const PHASE_LABELS: Record<PomodoroPhase, string> = {
  focus: "Focus",
  break: "Short break",
  long_break: "Long break",
};

// A ringing alarm, set when a phase ends. It keeps ringing (the clock in the
// header replays it every repeatAlarmSec) until acknowledged - any timer
// interaction - or until stopAlarmMin passes and it gives up.
export interface PomodoroAlarm {
  endedPhase: PomodoroPhase;
  startedAt: number;
}

interface PomodoroState {
  settings: PomodoroSettings;
  status: PomodoroStatus;
  phase: PomodoroPhase;
  endsAt: number | null; // epoch ms, set while running
  remainingMs: number | null; // set while paused
  taskId: string | null; // board task this block counts toward
  cycle: number; // focus blocks completed since the last long break
  doneToday: number;
  dayKey: string;
  alarm: PomodoroAlarm | null;
  start: () => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  // Called by the clock when the countdown hits zero.
  finishPhase: () => void;
  acknowledgeAlarm: () => void;
  setTask: (taskId: string | null) => void;
  updateSettings: (patch: Partial<PomodoroSettings>) => void;
}

export function phaseDurationMs(
  phase: PomodoroPhase,
  settings: PomodoroSettings,
): number {
  const minutes =
    phase === "focus"
      ? settings.workMin
      : phase === "break"
        ? settings.breakMin
        : settings.longBreakMin;
  return minutes * 60_000;
}

function todayKey(): string {
  return new Date().toLocaleDateString("en-CA"); // local YYYY-MM-DD
}

export const usePomodoroStore = create<PomodoroState>()(
  persist(
    (set, get) => ({
      settings: DEFAULT_SETTINGS,
      status: "idle",
      phase: "focus",
      endsAt: null,
      remainingMs: null,
      taskId: null,
      cycle: 0,
      doneToday: 0,
      dayKey: todayKey(),
      alarm: null,

      start: () => {
        const { status, phase, settings } = get();
        if (status !== "idle") return;
        set({
          status: "running",
          endsAt: Date.now() + phaseDurationMs(phase, settings),
          remainingMs: null,
          alarm: null,
        });
      },

      pause: () => {
        const { status, endsAt } = get();
        if (status !== "running" || endsAt == null) return;
        set({
          status: "paused",
          remainingMs: Math.max(0, endsAt - Date.now()),
          endsAt: null,
          alarm: null,
        });
      },

      resume: () => {
        const { status, remainingMs } = get();
        if (status !== "paused" || remainingMs == null) return;
        set({
          status: "running",
          endsAt: Date.now() + remainingMs,
          remainingMs: null,
          alarm: null,
        });
      },

      // Aborts the phase and returns to idle. A stopped focus block never
      // counts toward stats or the daily goal.
      stop: () =>
        set({
          status: "idle",
          phase: "focus",
          endsAt: null,
          remainingMs: null,
          alarm: null,
        }),

      finishPhase: () => {
        const state = get();
        if (state.status !== "running" || state.endsAt == null) return;
        if (state.endsAt > Date.now()) return;
        const { settings } = state;
        const alarm: PomodoroAlarm = {
          endedPhase: state.phase,
          startedAt: Date.now(),
        };

        if (state.phase === "focus") {
          const day = todayKey();
          const cycle = state.cycle + 1;
          const next: PomodoroPhase =
            cycle % settings.longBreakEvery === 0 ? "long_break" : "break";
          set({
            cycle,
            dayKey: day,
            doneToday: (state.dayKey === day ? state.doneToday : 0) + 1,
            phase: next,
            status: settings.autoStartBreak ? "running" : "idle",
            endsAt: settings.autoStartBreak
              ? Date.now() + phaseDurationMs(next, settings)
              : null,
            remainingMs: null,
            alarm,
          });
          return;
        }

        // A break ended: line up the next focus block, but let the human
        // start it - you may be away from the keyboard, so work never
        // begins on its own.
        set({
          phase: "focus",
          status: "idle",
          endsAt: null,
          remainingMs: null,
          alarm,
        });
      },

      acknowledgeAlarm: () => {
        if (get().alarm) set({ alarm: null });
      },

      setTask: (taskId) => set({ taskId }),

      updateSettings: (patch) =>
        set((state) => ({ settings: { ...state.settings, ...patch } })),
    }),
    {
      name: "jidoka-pomodoro",
      partialize: (state) => ({
        settings: state.settings,
        cycle: state.cycle,
        doneToday: state.doneToday,
        dayKey: state.dayKey,
        taskId: state.taskId,
      }),
    },
  ),
);
