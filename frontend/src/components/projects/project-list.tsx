"use client";

import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { projectColor } from "@/lib/project-palette";
import { COLUMNS, type Project } from "@/lib/types";
import type { ProjectTaskCounts } from "@/lib/project-task-counts";
import { DeleteProjectDialog } from "./delete-project-dialog";
import { ProjectDialog } from "./project-dialog";

// First line of the raw Markdown, good enough for a one-line row preview -
// full rendering happens in ProjectDialog's view mode.
function descriptionPreview(description: string): string {
  return description.split("\n").find((line) => line.trim().length > 0) ?? "";
}

function ProjectRow({
  project,
  colorIndex,
  counts,
}: {
  project: Project;
  colorIndex: number;
  counts: ProjectTaskCounts | undefined;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"view" | "edit">("view");
  // ProjectDialog only seeds its edit-mode fields from `project` on mount
  // (Radix's onOpenChange doesn't fire for an externally-toggled `open`
  // prop), so force a fresh mount each time this row opens it.
  const [dialogKey, setDialogKey] = useState(0);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  function openIn(nextMode: "view" | "edit") {
    setMode(nextMode);
    setDialogKey((k) => k + 1);
    setOpen(true);
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="w-full py-2 pr-2">
        <div className="flex items-center gap-2">
          <span
            className="size-1.5 shrink-0 rounded-full"
            style={{ backgroundColor: projectColor(colorIndex) }}
            aria-hidden
          />
          <button
            type="button"
            className="min-w-0 flex-1 rounded-md text-left outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
            onClick={() => openIn("view")}
          >
            <p className="truncate text-sm font-medium">{project.name}</p>
            {project.description && (
              <p className="truncate text-xs text-muted-foreground">
                {descriptionPreview(project.description)}
              </p>
            )}
          </button>
        </div>
      </td>
      {COLUMNS.map((column) => (
        <td
          key={column.id}
          className="hidden px-2 py-2 text-center font-mono text-xs tabular-nums text-muted-foreground sm:table-cell"
        >
          {counts?.[column.id] ?? 0}
        </td>
      ))}
      <td className="py-2 pl-2">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Edit ${project.name}`}
            onClick={() => openIn("edit")}
          >
            <Pencil />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={`Delete ${project.name}`}
            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            onClick={() => setConfirmingDelete(true)}
          >
            <Trash2 />
          </Button>
        </div>
      </td>
      <ProjectDialog
        key={dialogKey}
        project={project}
        open={open}
        onOpenChange={setOpen}
        initialMode={mode}
      />
      <DeleteProjectDialog
        project={project}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
      />
    </tr>
  );
}

export function ProjectList({
  projects,
  taskCounts,
}: {
  projects: Project[];
  taskCounts: Record<string, ProjectTaskCounts>;
}) {
  const ordered = [...projects].sort((a, b) =>
    a.createdAt.localeCompare(b.createdAt),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Projects</CardTitle>
      </CardHeader>
      <CardContent>
        {ordered.length === 0 ? (
          <p className="text-xs text-muted-foreground">
            No projects yet. Create one with &ldquo;Add project&rdquo; above.
          </p>
        ) : (
          <table className="w-full border-collapse">
            <thead>
              <tr>
                <th scope="col" className="sr-only">
                  Project
                </th>
                {COLUMNS.map((column) => (
                  <th
                    key={column.id}
                    scope="col"
                    className="hidden px-2 pb-1.5 text-center text-xs font-medium whitespace-nowrap text-muted-foreground sm:table-cell"
                  >
                    {column.title}
                  </th>
                ))}
                <th scope="col" className="sr-only">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((project, i) => (
                <ProjectRow
                  key={project.id}
                  project={project}
                  colorIndex={i}
                  counts={taskCounts[project.id]}
                />
              ))}
            </tbody>
          </table>
        )}
      </CardContent>
    </Card>
  );
}
