import { projectColor } from "@/lib/project-palette";
import type { Project } from "@/lib/types";

export function ChartLegend({ projects }: { projects: Project[] }) {
  const ordered = [...projects].sort((a, b) =>
    a.createdAt.localeCompare(b.createdAt),
  );
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5">
      {ordered.map((p, i) => (
        <li
          key={p.id}
          className="flex items-center gap-1.5 text-xs text-muted-foreground"
        >
          <span
            className="size-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: projectColor(i) }}
            aria-hidden
          />
          {p.name}
        </li>
      ))}
      <li className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          className="size-1.5 shrink-0 rounded-full bg-muted ring-1 ring-inset ring-foreground/10"
          aria-hidden
        />
        Not defined
      </li>
    </ul>
  );
}
