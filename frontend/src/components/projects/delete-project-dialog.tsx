"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { deleteProject } from "@/app/actions";
import type { Project } from "@/lib/types";

const CONFIRM_WORD = "delete";

export function DeleteProjectDialog({
  project,
  open,
  onOpenChange,
  onDeleted,
}: {
  project: Project;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted?: () => void;
}) {
  const [confirmText, setConfirmText] = useState("");
  const [pending, setPending] = useState(false);
  const confirmed = confirmText.trim().toLowerCase() === CONFIRM_WORD;

  async function handleDelete() {
    if (!confirmed || pending) return;
    setPending(true);
    try {
      await deleteProject(project.id);
      setConfirmText("");
      onOpenChange(false);
      onDeleted?.();
      toast.success("Project deleted", { description: project.name });
    } catch (error) {
      console.error("Could not delete project:", error);
      toast.error("Couldn't delete project", {
        description: "Nothing was removed. Check the connection and try again.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (pending) return;
        onOpenChange(next);
        if (!next) setConfirmText("");
      }}
    >
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Delete &ldquo;{project.name}&rdquo;?</DialogTitle>
          <DialogDescription>
            This is destructive and can&apos;t be undone. The project and its
            description are permanently deleted; tasks linked to it are
            unlinked, not deleted.
          </DialogDescription>
        </DialogHeader>
        <form
          className="flex flex-col gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            handleDelete();
          }}
        >
          <label
            htmlFor="delete-project-confirm"
            className="text-xs font-medium text-muted-foreground"
          >
            Type <span className="font-mono text-foreground">delete</span> to
            confirm
          </label>
          <Input
            id="delete-project-confirm"
            autoFocus
            autoComplete="off"
            aria-describedby="delete-project-confirm-hint"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="delete"
          />
        </form>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={!confirmed || pending}
            onClick={handleDelete}
          >
            {pending ? "Deleting…" : "Delete project"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
