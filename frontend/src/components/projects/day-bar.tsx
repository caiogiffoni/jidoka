import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { projectColor } from "@/lib/project-palette";
import { formatMinutes, type ChartDay } from "@/lib/weekly-chart";
import { cn } from "@/lib/utils";

export function DayBar({
  day,
  axisCeiling,
}: {
  day: ChartDay;
  axisCeiling: number;
}) {
  const visible = day.segments.filter((s) => s.minutes > 0);

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className="flex h-40 w-6 flex-col-reverse gap-0.5"
        role="group"
        aria-label={day.label}
      >
        {visible.length === 0 ? (
          <div className="h-px w-full bg-border" aria-hidden />
        ) : (
          visible.map((segment, i) => {
            // flex-col-reverse renders the last array item at the top of
            // the stack - the outward end, the only place the cap rounds.
            const isOutwardEnd = i === visible.length - 1;
            const heightPct = (segment.minutes / axisCeiling) * 100;
            return (
              <Tooltip key={segment.projectId ?? "none"}>
                <TooltipTrigger asChild>
                  <div
                    tabIndex={0}
                    role="img"
                    aria-label={`${segment.name}: ${formatMinutes(segment.minutes)} on ${day.label}`}
                    style={{
                      height: `${heightPct}%`,
                      backgroundColor:
                        segment.projectId === null
                          ? undefined
                          : projectColor(segment.colorIndex!),
                    }}
                    className={cn(
                      "w-full shrink-0 outline-none transition-[filter] duration-150 hover:brightness-110 focus-visible:brightness-110 focus-visible:ring-2 focus-visible:ring-ring/50",
                      isOutwardEnd && "rounded-t-[4px]",
                      // Machine Gray alone is near-invisible on a white
                      // card at full opacity; the hairline ring borrows
                      // the app's existing flat-surface vocabulary rather
                      // than inventing a new gray value.
                      segment.projectId === null &&
                        "bg-muted ring-1 ring-inset ring-foreground/10",
                    )}
                  />
                </TooltipTrigger>
                <TooltipContent side="top">
                  <div className="font-mono text-sm font-medium tabular-nums">
                    {formatMinutes(segment.minutes)}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {day.label} · {segment.name}
                  </div>
                </TooltipContent>
              </Tooltip>
            );
          })
        )}
      </div>
      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
        {day.label}
      </span>
    </div>
  );
}
