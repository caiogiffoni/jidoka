"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Project } from "@/lib/types";
import {
  formatMinutes,
  niceAxisCeiling,
  type ChartDay,
} from "@/lib/weekly-chart";
import { ChartLegend } from "./chart-legend";
import { DayBar } from "./day-bar";

export function WeeklyBarChart({
  days,
  projects,
}: {
  days: ChartDay[];
  projects: Project[];
}) {
  const weekTotal = days.reduce((sum, d) => sum + d.total, 0);
  const maxDay = Math.max(0, ...days.map((d) => d.total));
  const axisCeiling = niceAxisCeiling(maxDay);
  const gridlines = [axisCeiling, axisCeiling / 2, 0];
  const hasData = weekTotal > 0;

  return (
    <TooltipProvider>
      <Card>
        <CardHeader className="flex flex-row items-baseline justify-between">
          <CardTitle>Time this week</CardTitle>
          <span className="font-mono text-sm tabular-nums text-muted-foreground">
            {formatMinutes(weekTotal)}
          </span>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {!hasData ? (
            <div className="flex h-40 flex-col items-center justify-end gap-2">
              <div className="h-px w-full bg-border" />
              <p className="pb-2 text-xs text-muted-foreground">
                {projects.length === 0
                  ? "No projects yet. Create one, then log a pomodoro to see it here."
                  : "No focus time logged this week."}
              </p>
            </div>
          ) : (
            <div className="flex gap-2">
              <div className="flex h-40 flex-col justify-between font-mono text-[11px] tabular-nums text-muted-foreground">
                {gridlines.map((m) => (
                  <span key={m}>{m}m</span>
                ))}
              </div>
              <div className="flex flex-1 items-end justify-between gap-3 border-l border-border pl-3">
                {days.map((day) => (
                  <DayBar key={day.date} day={day} axisCeiling={axisCeiling} />
                ))}
              </div>
            </div>
          )}
          <div className="border-t pt-3">
            <ChartLegend projects={projects} />
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  );
}
