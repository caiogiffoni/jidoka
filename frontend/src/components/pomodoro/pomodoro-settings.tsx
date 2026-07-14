"use client";

import { useState } from "react";
import { Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Slider } from "@/components/ui/slider";
import { ALARM_SOUNDS, type AlarmSound } from "@/lib/alarm";
import {
  usePomodoroStore,
  type PomodoroSettings,
} from "@/stores/pomodoro-store";

export function PomodoroSettingsDialog() {
  const [open, setOpen] = useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground hover:text-foreground"
          aria-label="Timer settings"
        >
          <Settings />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xs">
        {/* Keyed on open so the form re-reads the store each time. */}
        {open && <SettingsForm close={() => setOpen(false)} />}
      </DialogContent>
    </Dialog>
  );
}

// Numeric fields are held as strings while editing so clearing an input
// doesn't fight the user; values are parsed and clamped on save.
interface FormState {
  workMin: string;
  breakMin: string;
  longBreakMin: string;
  longBreakEvery: string;
  volume: number;
  alarmSound: AlarmSound;
  repeatAlarmSec: string;
  stopAlarmMin: string;
  autoStartBreak: boolean;
  dailyGoal: string;
}

function clamp(raw: string, min: number, max: number, fallback: number) {
  const n = Number.parseInt(raw, 10);
  return Number.isNaN(n) ? fallback : Math.min(max, Math.max(min, n));
}

function SettingsForm({ close }: { close: () => void }) {
  const settings = usePomodoroStore((s) => s.settings);
  const updateSettings = usePomodoroStore((s) => s.updateSettings);
  const [form, setForm] = useState<FormState>({
    workMin: String(settings.workMin),
    breakMin: String(settings.breakMin),
    longBreakMin: String(settings.longBreakMin),
    longBreakEvery: String(settings.longBreakEvery),
    volume: settings.volume,
    alarmSound: settings.alarmSound,
    repeatAlarmSec: String(settings.repeatAlarmSec),
    stopAlarmMin: String(settings.stopAlarmMin),
    autoStartBreak: settings.autoStartBreak,
    dailyGoal: String(settings.dailyGoal),
  });

  function patch<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function save() {
    const next: PomodoroSettings = {
      workMin: clamp(form.workMin, 1, 180, settings.workMin),
      breakMin: clamp(form.breakMin, 1, 60, settings.breakMin),
      longBreakMin: clamp(form.longBreakMin, 1, 90, settings.longBreakMin),
      longBreakEvery: clamp(form.longBreakEvery, 1, 12, settings.longBreakEvery),
      volume: form.volume,
      alarmSound: form.alarmSound,
      repeatAlarmSec: clamp(form.repeatAlarmSec, 1, 60, settings.repeatAlarmSec),
      stopAlarmMin: clamp(form.stopAlarmMin, 1, 30, settings.stopAlarmMin),
      autoStartBreak: form.autoStartBreak,
      dailyGoal: clamp(form.dailyGoal, 0, 24, settings.dailyGoal),
    };
    updateSettings(next);
    close();
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        save();
      }}
    >
      <DialogHeader>
        <DialogTitle>Timer settings</DialogTitle>
      </DialogHeader>

      <div className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-2">
        <NumberRow
          id="pomo-work"
          label="Work duration"
          unit="min"
          value={form.workMin}
          onChange={(v) => patch("workMin", v)}
        />
        <NumberRow
          id="pomo-break"
          label="Break duration"
          unit="min"
          value={form.breakMin}
          onChange={(v) => patch("breakMin", v)}
        />
        <NumberRow
          id="pomo-long-break"
          label="Long break duration"
          unit="min"
          value={form.longBreakMin}
          onChange={(v) => patch("longBreakMin", v)}
        />
        <NumberRow
          id="pomo-long-every"
          label="Long break every"
          unit="blocks"
          value={form.longBreakEvery}
          onChange={(v) => patch("longBreakEvery", v)}
        />

        <label htmlFor="pomo-volume" className="text-sm text-muted-foreground">
          Volume
        </label>
        <div className="flex items-center justify-end gap-2">
          <Slider
            id="pomo-volume"
            className="w-24"
            min={0}
            max={100}
            step={5}
            value={[form.volume]}
            onValueChange={([v]) => patch("volume", v)}
            aria-label="Alarm volume"
          />
          <span className="w-8 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
            {form.volume}
          </span>
        </div>

        <label htmlFor="pomo-sound" className="text-sm text-muted-foreground">
          Alarm sound
        </label>
        <NativeSelect
          id="pomo-sound"
          className="w-28 justify-self-end"
          value={form.alarmSound}
          onChange={(e) => patch("alarmSound", e.target.value as AlarmSound)}
        >
          {ALARM_SOUNDS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </NativeSelect>

        <NumberRow
          id="pomo-repeat"
          label="Repeat alarm every"
          unit="sec"
          value={form.repeatAlarmSec}
          onChange={(v) => patch("repeatAlarmSec", v)}
        />
        <NumberRow
          id="pomo-stop-alarm"
          label="Stop alarm after"
          unit="min"
          value={form.stopAlarmMin}
          onChange={(v) => patch("stopAlarmMin", v)}
        />

        <label
          htmlFor="pomo-auto-break"
          className="text-sm text-muted-foreground"
        >
          Auto-start break
        </label>
        <div className="flex justify-end pr-1">
          <Checkbox
            id="pomo-auto-break"
            checked={form.autoStartBreak}
            onCheckedChange={(v) => patch("autoStartBreak", v === true)}
          />
        </div>

        <NumberRow
          id="pomo-goal"
          label="Daily goal"
          unit="blocks"
          min={0}
          value={form.dailyGoal}
          onChange={(v) => patch("dailyGoal", v)}
        />
      </div>

      <p className="text-xs text-muted-foreground">
        The daily goal counts finished work blocks; 0 turns it off.
      </p>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={close}>
          Cancel
        </Button>
        <Button type="submit">Save</Button>
      </DialogFooter>
    </form>
  );
}

function NumberRow({
  id,
  label,
  unit,
  value,
  onChange,
  min = 1,
}: {
  id: string;
  label: string;
  unit: string;
  value: string;
  onChange: (value: string) => void;
  min?: number;
}) {
  return (
    <>
      <label htmlFor={id} className="text-sm text-muted-foreground">
        {label}
      </label>
      <div className="flex items-center justify-end gap-1.5">
        <Input
          id={id}
          type="number"
          inputMode="numeric"
          min={min}
          className="h-7 w-16 text-right md:text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <span className="w-9 text-xs text-muted-foreground">{unit}</span>
      </div>
    </>
  );
}
