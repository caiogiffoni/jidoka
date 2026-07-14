"use client";

import { useEffect, useState } from "react";
import { Pause, Play, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { NativeSelect } from "@/components/ui/native-select";
import { useBoardStore } from "@/stores/board-store";
import {
  PHASE_LABELS,
  phaseDurationMs,
  usePomodoroStore,
} from "@/stores/pomodoro-store";
import { playAlarm } from "@/lib/alarm";
import { COLUMNS } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PomodoroSettingsDialog } from "./pomodoro-settings";
import { TomatoIcon } from "./tomato-icon";

function formatMs(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export function PomodoroMenu() {
  const status = usePomodoroStore((s) => s.status);
  const phase = usePomodoroStore((s) => s.phase);
  const endsAt = usePomodoroStore((s) => s.endsAt);
  const remainingMs = usePomodoroStore((s) => s.remainingMs);
  const settings = usePomodoroStore((s) => s.settings);
  const taskId = usePomodoroStore((s) => s.taskId);
  const doneToday = usePomodoroStore((s) => s.doneToday);
  const start = usePomodoroStore((s) => s.start);
  const pause = usePomodoroStore((s) => s.pause);
  const resume = usePomodoroStore((s) => s.resume);
  const stop = usePomodoroStore((s) => s.stop);
  const setTask = usePomodoroStore((s) => s.setTask);
  const alarm = usePomodoroStore((s) => s.alarm);
  const acknowledgeAlarm = usePomodoroStore((s) => s.acknowledgeAlarm);
  const tasks = useBoardStore((s) => s.tasks);

  // The clock: ticks while running and fires the phase change at zero. It
  // lives here (always mounted in the header) so the timer survives the
  // popover closing. `now` is only written in event handlers and the
  // interval callback - render stays pure.
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => {
      setNow(Date.now());
      const s = usePomodoroStore.getState();
      if (s.status === "running" && s.endsAt != null && s.endsAt <= Date.now()) {
        s.finishPhase();
      }
    }, 250);
    return () => clearInterval(id);
  }, [status]);

  // The alarm: rings when a phase ends and keeps ringing every
  // repeatAlarmSec until acknowledged (any timer interaction) or until
  // stopAlarmMin passes and it gives up on its own.
  useEffect(() => {
    if (!alarm) return;
    const initial = usePomodoroStore.getState().settings;
    playAlarm(initial.alarmSound, initial.volume);
    const id = setInterval(
      () => {
        const s = usePomodoroStore.getState();
        if (!s.alarm) return;
        if (
          Date.now() - s.alarm.startedAt >=
          s.settings.stopAlarmMin * 60_000
        ) {
          s.acknowledgeAlarm();
          return;
        }
        playAlarm(s.settings.alarmSound, s.settings.volume);
      },
      Math.max(1, initial.repeatAlarmSec) * 1000,
    );
    return () => clearInterval(id);
  }, [alarm]);

  function handleStart() {
    setNow(Date.now());
    start();
  }

  function handleResume() {
    setNow(Date.now());
    resume();
  }

  const duration = phaseDurationMs(phase, settings);
  const remaining =
    status === "running" && endsAt != null
      ? Math.max(0, endsAt - now)
      : status === "paused" && remainingMs != null
        ? remainingMs
        : duration;
  const progress = status === "idle" ? 0 : 1 - remaining / duration;

  return (
    <Popover
      onOpenChange={(open) => {
        // Opening the timer counts as hearing the alarm.
        if (open) acknowledgeAlarm();
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size={status === "idle" ? "icon" : "default"}
          aria-label={
            status === "idle"
              ? "Pomodoro timer"
              : `Pomodoro timer: ${PHASE_LABELS[phase]}, ${formatMs(remaining)} left`
          }
        >
          <TomatoIcon
            className={cn(
              "size-4",
              alarm != null && "motion-safe:animate-pulse",
            )}
          />
          {status !== "idle" && (
            <span
              className={cn(
                "font-mono text-xs tabular-nums",
                status === "paused" && "text-muted-foreground",
              )}
            >
              {formatMs(remaining)}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground">
            {PHASE_LABELS[phase]}
          </span>
          <div className="flex items-center gap-1.5">
            {(doneToday > 0 || settings.dailyGoal > 0) && (
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {settings.dailyGoal > 0
                  ? `${doneToday}/${settings.dailyGoal} today`
                  : `${doneToday} today`}
              </span>
            )}
            <PomodoroSettingsDialog />
          </div>
        </div>

        <div className="text-center font-mono text-4xl font-medium tracking-tight tabular-nums">
          {formatMs(remaining)}
        </div>

        <div className="h-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full origin-left bg-primary transition-transform duration-300 ease-linear"
            style={{ transform: `scaleX(${progress})` }}
          />
        </div>

        <label className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            Task
          </span>
          <NativeSelect
            value={taskId ?? ""}
            onChange={(e) => setTask(e.target.value || null)}
          >
            <option value="">No task</option>
            {COLUMNS.map(
              (column) =>
                tasks[column.id].length > 0 && (
                  <optgroup key={column.id} label={column.title}>
                    {tasks[column.id].map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.title}
                      </option>
                    ))}
                  </optgroup>
                ),
            )}
          </NativeSelect>
        </label>

        {status === "idle" ? (
          <Button className="w-full" onClick={handleStart}>
            <Play data-icon="inline-start" />
            Start {PHASE_LABELS[phase].toLowerCase()}
          </Button>
        ) : (
          <div className="flex gap-2">
            {status === "running" ? (
              <Button variant="outline" className="flex-1" onClick={pause}>
                <Pause data-icon="inline-start" />
                Pause
              </Button>
            ) : (
              <Button className="flex-1" onClick={handleResume}>
                <Play data-icon="inline-start" />
                Resume
              </Button>
            )}
            <Button variant="destructive" className="flex-1" onClick={stop}>
              <Square data-icon="inline-start" />
              Stop
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
