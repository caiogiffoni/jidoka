"use client";

import { useState } from "react";
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
import { updateProject } from "@/app/actions";
import type { Project } from "@/lib/types";
import { DeleteProjectDialog } from "./delete-project-dialog";
import { ProjectDescription } from "./project-description";

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
  const [saving, setSaving] = useState(false);

  function startEditing() {
    setName(project.name);
    setDescription(project.description ?? "");
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
      <DialogContent>
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
              <Textarea
                id="project-description"
                value={description}
                placeholder="What is this project about…"
                className="min-h-32"
                onChange={(e) => setDescription(e.target.value)}
              />
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
                <ProjectDescription text={project.description} />
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No description
                </p>
              )}
            </div>
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
