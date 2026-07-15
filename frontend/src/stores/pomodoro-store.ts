import { create } from "zustand";
import { persist } from "zustand/middleware";
import { toast } from "sonner";
import { recordWorkBlock } from "@/app/actions";
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
  // Called once after rehydration: walks the timer through any phases that
  // expired while the page was closed or hidden.
  catchUp: () => void;
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

function dayKeyOf(date: Date): string {
  return date.toLocaleDateString("en-CA"); // local YYYY-MM-DD
}

function todayKey(): string {
  return dayKeyOf(new Date());
}

// Fire-and-forget persistence of a completed focus block. Stopped (aborted)
// sessions never call this - only a block that finishes counts. Blocks
// without a linked task have nowhere to attach, so they stay client-side.
// A failed save never disturbs the timer - the user just loses one history
// row.
function persistFocusBlock(
  taskId: string | null,
  startedAt: number,
  endedAt: number,
): void {
  if (!taskId || endedAt <= startedAt) return;
  recordWorkBlock({ taskId, startedAt, endedAt }).catch((error) => {
    console.error("Could not save work block:", error);
    toast.error("Couldn't save the work block", {
      description: "The timer is unaffected, but this block wasn't recorded.",
    });
  });
}

// The transition applied when a running phase's countdown reaches its end
// with the page open - the only way a phase completes; expiring while the
// page is closed never counts (see catchUp). `endedAt` is the phase's real
// end, so follow-up phases are scheduled from it, not from Date.now().
function advance(
  state: Pick<
    PomodoroState,
    "settings" | "phase" | "cycle" | "doneToday" | "dayKey"
  >,
  endedAt: number,
): Partial<PomodoroState> {
  const { settings } = state;
  if (state.phase === "focus") {
    const day = dayKeyOf(new Date(endedAt));
    const cycle = state.cycle + 1;
    const next: PomodoroPhase =
      cycle % settings.longBreakEvery === 0 ? "long_break" : "break";
    return {
      cycle,
      dayKey: day,
      doneToday: (state.dayKey === day ? state.doneToday : 0) + 1,
      phase: next,
      status: settings.autoStartBreak ? "running" : "idle",
      endsAt: settings.autoStartBreak
        ? endedAt + phaseDurationMs(next, settings)
        : null,
      remainingMs: null,
    };
  }
  // A break ended: line up the next focus block, but let the human start
  // it - they may be away from the keyboard, so work never begins on its own.
  return { phase: "focus", status: "idle", endsAt: null, remainingMs: null };
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
      // counts toward stats or the daily goal, and is never persisted -
      // only a block that finishes is worth keeping.
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
        if (state.phase === "focus") {
          persistFocusBlock(
            state.taskId,
            state.endsAt - phaseDurationMs("focus", state.settings),
            state.endsAt,
          );
        }
        set({
          ...advance(state, state.endsAt),
          alarm: { endedPhase: state.phase, startedAt: Date.now() },
        });
      },

      catchUp: () => {
        const state = get();
        if (
          state.status !== "running" ||
          state.endsAt == null ||
          state.endsAt > Date.now()
        ) {
          return;
        }
        // The phase expired while the page was closed. The user may not
        // have been working, so the block is discarded entirely: no stats,
        // no daily goal, no alarm, no POST.
        set({
          status: "idle",
          phase: "focus",
          endsAt: null,
          remainingMs: null,
          alarm: null,
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
      // endsAt is absolute, so a persisted running timer stays correct
      // across reloads; catchUp() settles anything that expired meanwhile.
      partialize: (state) => ({
        settings: state.settings,
        cycle: state.cycle,
        doneToday: state.doneToday,
        dayKey: state.dayKey,
        taskId: state.taskId,
        status: state.status,
        phase: state.phase,
        endsAt: state.endsAt,
        remainingMs: state.remainingMs,
      }),
      // Hydrate explicitly on mount (see PomodoroMenu): the header button
      // renders persisted state, so hydrating during SSR-render would
      // mismatch the server HTML.
      skipHydration: true,
    },
  ),
);
