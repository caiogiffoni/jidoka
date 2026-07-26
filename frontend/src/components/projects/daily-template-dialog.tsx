"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { ChecklistItemEditor } from "@/components/checklist-item-editor";
import { COLUMNS, type DailyTemplate } from "@/lib/types";
import { cn } from "@/lib/utils";

// Mirrors the real "Add task" dialog's shape (Title, Description,
// Checklist, Project, Column) since that's what the user asked to trigger
// here - but it never calls the task API. "Save template" hands
// title/description/checklist back to the caller (a project's daily
// template); Project and Column are shown for visual consistency only -
// a generated card always belongs to this project and always lands in
// To Do, so those two controls are disabled rather than wired to anything.
// Title is optional too - the generated card is always named after the
// project and date, with this appended rather than replacing that name.
export function DailyTemplateDialog({
  open,
  onOpenChange,
  projectName,
  initialTemplate,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectName: string;
  initialTemplate: DailyTemplate | null;
  onSave: (template: DailyTemplate) => void;
}) {
  const [title, setTitle] = useState(initialTemplate?.title ?? "");
  const [description, setDescription] = useState(
    initialTemplate?.description ?? "",
  );
  const [checklist, setChecklist] = useState<string[]>(
    initialTemplate?.checklist ?? [],
  );

  // Reseed from what's actually saved every time the popup opens, so a
  // previous cancel never leaks into the next open - adjusted during render
  // rather than in an effect, to avoid an extra render pass.
  const [prevOpen, setPrevOpen] = useState(open);
  if (open !== prevOpen) {
    setPrevOpen(open);
    if (open) {
      setTitle(initialTemplate?.title ?? "");
      setDescription(initialTemplate?.description ?? "");
      setChecklist(initialTemplate?.checklist ?? []);
    }
  }

  function save() {
    onSave({
      title: title.trim() || undefined,
      description: description.trim() || undefined,
      checklist: checklist.map((item) => item.trim()).filter(Boolean),
    });
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Daily task template</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="daily-template-title"
              className="text-xs font-medium text-muted-foreground"
            >
              Title <span className="font-normal">(optional)</span>
            </label>
            <Input
              id="daily-template-title"
              autoFocus
              value={title}
              placeholder="Appended to the generated card's name…"
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="daily-template-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description <span className="font-normal">(optional)</span>
            </label>
            <Textarea
              id="daily-template-description"
              value={description}
              placeholder="Add a description…"
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Checklist <span className="font-normal">(optional)</span>
            </span>
            <ChecklistItemEditor items={checklist} onChange={setChecklist} />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Project
            </span>
            <NativeSelect value={projectName} disabled>
              <option>{projectName || "This project"}</option>
            </NativeSelect>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              Column
            </span>
            <div className="flex gap-1.5">
              {COLUMNS.map((column) => (
                <Button
                  key={column.id}
                  type="button"
                  variant={column.id === "todo" ? "secondary" : "ghost"}
                  size="sm"
                  disabled
                  className={cn(
                    "flex-1",
                    column.id === "todo" && "ring-1 ring-ring/40",
                  )}
                >
                  {column.title}
                </Button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground italic">
              A generated card always belongs to this project and lands in
              To Do.
            </p>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit">Save template</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
