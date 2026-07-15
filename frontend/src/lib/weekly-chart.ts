import type { ApiDailyProjectMinutes } from "./api";
import type { Project } from "./types";

export interface ChartSegment {
  projectId: string | null;
  name: string;
  colorSlot: number | null; // null => "Not defined" (Machine Gray, never a palette slot)
  minutes: number;
}

export interface ChartDay {
  date: string; // "YYYY-MM-DD", UTC
  label: string; // "Mon 7/8"
  segments: ChartSegment[]; // real projects (colorSlot asc) then "Not defined" last
  total: number;
}

const NOT_DEFINED = "Not defined";

function utcDateKey(epochMs: number): string {
  return new Date(epochMs).toISOString().slice(0, 10);
}

function shortLabel(dateKey: string): string {
  const d = new Date(`${dateKey}T00:00:00Z`);
  const weekday = d.toLocaleDateString("en-US", {
    weekday: "short",
    timeZone: "UTC",
  });
  const md = d.toLocaleDateString("en-US", {
    month: "numeric",
    day: "numeric",
    timeZone: "UTC",
  });
  return `${weekday} ${md}`;
}

// Zero-fills the dense date x project grid the stacked bar chart needs -
// the stats endpoint only emits rows where real time was logged.
export function buildWeeklyChart(
  projects: Project[],
  stats: ApiDailyProjectMinutes[],
  days = 7,
): ChartDay[] {
  const now = new Date();
  const todayUtcMs = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
  );
  const dateKeys = Array.from({ length: days }, (_, i) =>
    utcDateKey(todayUtcMs - (days - 1 - i) * 86_400_000),
  );

  // date -> (project id, or "__none__" for "Not defined") -> minutes
  const lookup = new Map<string, Map<string, number>>();
  for (const row of stats) {
    const key = row.project_id ?? "__none__";
    if (!lookup.has(row.date)) lookup.set(row.date, new Map());
    lookup.get(row.date)!.set(key, row.minutes);
  }

  const orderedProjects = [...projects].sort(
    (a, b) => a.colorSlot - b.colorSlot,
  );

  return dateKeys.map((date) => {
    const dayLookup = lookup.get(date);
    const segments: ChartSegment[] = orderedProjects.map((p) => ({
      projectId: p.id,
      name: p.name,
      colorSlot: p.colorSlot,
      minutes: dayLookup?.get(p.id) ?? 0,
    }));
    segments.push({
      projectId: null,
      name: NOT_DEFINED,
      colorSlot: null,
      minutes: dayLookup?.get("__none__") ?? 0,
    });
    return {
      date,
      label: shortLabel(date),
      segments,
      total: segments.reduce((sum, s) => sum + s.minutes, 0),
    };
  });
}

// Rounds a max-day-total up to a "clean" axis ceiling for gridlines.
export function niceAxisCeiling(maxMinutes: number): number {
  const steps = [15, 30, 45, 60, 90, 120, 180, 240, 300, 360, 480, 600];
  for (const step of steps) if (maxMinutes <= step) return step;
  return Math.ceil(maxMinutes / 60) * 60;
}

export function formatMinutes(minutes: number): string {
  const rounded = Math.round(minutes);
  if (rounded < 60) return `${rounded}m`;
  const h = Math.floor(rounded / 60);
  const m = rounded % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}
