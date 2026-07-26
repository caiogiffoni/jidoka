"use client";

import { useRef, useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownText } from "@/components/ui/markdown-text";
import { MarkdownToolbar } from "@/components/markdown-toolbar";
import { updateProject } from "@/app/actions";
import type { DailyTemplate, Project } from "@/lib/types";
import { DeleteProjectDialog } from "./delete-project-dialog";
import { DailyTemplateField } from "./daily-template-field";

export function ProjectDialog({
  project,
  open,
  onOpenChange,
  initialMode = "view",
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialMode?: "view" | "edit";
}) {
  const [editing, setEditing] = useState(initialMode === "edit");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [name, setName] = useState(initialMode === "edit" ? project.name : "");
  const [description, setDescription] = useState(
    initialMode === "edit" ? (project.description ?? "") : "",
  );
  const [dailyEnabled, setDailyEnabled] = useState(
    initialMode === "edit" ? project.dailyEnabled : false,
  );
  const [dailyTemplate, setDailyTemplate] = useState<DailyTemplate | null>(
    initialMode === "edit" ? project.dailyTemplate : null,
  );
  const [saving, setSaving] = useState(false);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  function startEditing() {
    setName(project.name);
    setDescription(project.description ?? "");
    setDailyEnabled(project.dailyEnabled);
    setDailyTemplate(project.dailyTemplate);
    setEditing(true);
  }

  async function save() {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      await updateProject({
        id: project.id,
        name: trimmed,
        description: description.trim() || undefined,
        dailyEnabled,
        dailyTemplate,
      });
      setEditing(false);
    } catch (error) {
      console.error("Could not update project:", error);
      toast.error("Couldn't save project", {
        description: "Nothing was saved. Check the connection and try again.",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) setEditing(false);
      }}
    >
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        {editing ? (
          <form
            className="flex flex-col gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            <DialogHeader>
              <DialogTitle>Edit project</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="project-name"
                className="text-xs font-medium text-muted-foreground"
              >
                Name
              </label>
              <Input
                id="project-name"
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="project-description"
                className="text-xs font-medium text-muted-foreground"
              >
                Description{" "}
                <span className="font-normal">(Markdown supported)</span>
              </label>
              <MarkdownToolbar
                textareaRef={descriptionRef}
                value={description}
                onChange={setDescription}
              />
              <Textarea
                id="project-description"
                ref={descriptionRef}
                value={description}
                placeholder="What is this project about…"
                className="min-h-32 rounded-t-none border-t-0"
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <DailyTemplateField
              projectName={name}
              dailyEnabled={dailyEnabled}
              onDailyEnabledChange={setDailyEnabled}
              dailyTemplate={dailyTemplate}
              onDailyTemplateChange={setDailyTemplate}
            />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={saving}
                onClick={() => setEditing(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={!name.trim() || saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="pr-24 leading-snug">
                {project.name}
              </DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                Description
              </span>
              {project.description ? (
                <MarkdownText text={project.description} />
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No description
                </p>
              )}
            </div>
            {project.dailyEnabled && project.dailyTemplate && (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Daily task template
                </span>
                {project.dailyTemplate.title && (
                  <p className="text-sm">{project.dailyTemplate.title}</p>
                )}
                {project.dailyTemplate.checklist.length > 0 && (
                  <ul className="list-inside list-disc text-sm text-muted-foreground">
                    {project.dailyTemplate.checklist.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            <Button
              variant="ghost"
              size="icon-sm"
              className="absolute top-2 right-10"
              onClick={startEditing}
            >
              <Pencil />
              <span className="sr-only">Edit project</span>
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="absolute top-2 right-18 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 />
              <span className="sr-only">Delete project</span>
            </Button>
          </>
        )}
      </DialogContent>
      <DeleteProjectDialog
        project={project}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        onDeleted={() => onOpenChange(false)}
      />
    </Dialog>
  );
}
