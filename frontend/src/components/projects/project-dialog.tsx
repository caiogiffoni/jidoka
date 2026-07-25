"use client";

import { useRef, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import type { Project } from "@/lib/types";
import { DeleteProjectDialog } from "./delete-project-dialog";

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
  const [dailyTemplate, setDailyTemplate] = useState<string[]>(
    initialMode === "edit" ? project.dailyTemplate : [],
  );
  const [saving, setSaving] = useState(false);
  const descriptionRef = useRef<HTMLTextAreaElement>(null);
  const itemRefs = useRef<(HTMLInputElement | null)[]>([]);

  function startEditing() {
    setName(project.name);
    setDescription(project.description ?? "");
    setDailyEnabled(project.dailyEnabled);
    setDailyTemplate(project.dailyTemplate);
    setEditing(true);
  }

  function updateTemplateItem(index: number, value: string) {
    setDailyTemplate((items) => items.map((it, i) => (i === index ? value : it)));
  }

  function removeTemplateItem(index: number) {
    setDailyTemplate((items) => items.filter((_, i) => i !== index));
  }

  // Focus the newly added row so typing can continue right away - without
  // this, focus stays on the "Add item" button and a space in what you type
  // next re-clicks it (native button behavior), silently adding blank rows.
  function addTemplateItem() {
    setDailyTemplate((items) => [...items, ""]);
    requestAnimationFrame(() => {
      itemRefs.current[itemRefs.current.length - 1]?.focus();
    });
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
        dailyTemplate: dailyTemplate.map((item) => item.trim()).filter(Boolean),
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
            <div className="flex flex-col gap-2 rounded-md border p-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <Checkbox
                  checked={dailyEnabled}
                  onCheckedChange={(checked) => setDailyEnabled(checked === true)}
                />
                Generate a daily checklist card
              </label>
              {dailyEnabled && (
                <div className="flex flex-col gap-1.5 pl-6">
                  <span className="text-xs text-muted-foreground">
                    One card is created each day titled &ldquo;Daily -
                    DD-MM-YY - {project.name}&rdquo;, with each line below as
                    a checklist item.
                  </span>
                  {dailyTemplate.map((item, index) => (
                    <div key={index} className="flex items-center gap-1.5">
                      <Input
                        ref={(el) => {
                          itemRefs.current[index] = el;
                        }}
                        value={item}
                        placeholder="e.g. write a check-in message in Slack"
                        onChange={(e) => updateTemplateItem(index, e.target.value)}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Remove item"
                        className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        onClick={() => removeTemplateItem(index)}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="self-start"
                    onClick={addTemplateItem}
                  >
                    <Plus /> Add item
                  </Button>
                </div>
              )}
            </div>
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
            {project.dailyEnabled && project.dailyTemplate.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs font-medium text-muted-foreground">
                  Daily checklist
                </span>
                <ul className="list-inside list-disc text-sm text-muted-foreground">
                  {project.dailyTemplate.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
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
