"use client";

import { useEffect, useRef, useState } from "react";
import { Archive, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
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
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";
import { MarkdownText } from "@/components/ui/markdown-text";
import { MarkdownToolbar } from "@/components/markdown-toolbar";
import { cn } from "@/lib/utils";
import { useBoardStore } from "@/stores/board-store";
import {
  fetchTaskMinutes,
  logWorkBlock,
  updateTask as persistTaskUpdate,
} from "@/app/actions";
import { formatMinutes } from "@/lib/weekly-chart";
import { formatDueDate, isOverdue } from "@/lib/due-date";
import { COLUMNS, type ChecklistItem, type Project, type Task } from "@/lib/types";
import { ConfirmDeleteDialog } from "./delete-task";
import { archiveTaskWithUndo } from "./archive-task";

export function TaskDialog({
  task,
  projects,
  open,
  onOpenChange,
}: {
  task: Task;
  projects: Project[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const updateTask = useBoardStore((s) => s.updateTask);
  const columnOf = useBoardStore((s) => s.columnOf);
  const [editing, setEditing] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [projectId, setProjectId] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [minutesInput, setMinutesInput] = useState("");
  const [loggingTime, setLoggingTime] = useState(false);
  const [totalMinutes, setTotalMinutes] = useState<number | null>(null);
  const [newItemText, setNewItemText] = useState("");
  const descriptionRef = useRef<HTMLTextAreaElement>(null);

  const columnId = columnOf(task.id);
  const columnTitle = COLUMNS.find((c) => c.id === columnId)?.title;
  const project = projects.find((p) => p.id === task.projectId);

  // Refetch whenever the dialog opens or the task changes, and again after a
  // successful manual log so the total reflects what was just added.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetchTaskMinutes(task.id)
      .then((minutes) => {
        if (!cancelled) setTotalMinutes(minutes);
      })
      .catch((error) => {
        console.error("Could not load logged time:", error);
      });
    return () => {
      cancelled = true;
    };
  }, [open, task.id]);

  function startEditing() {
    setTitle(task.title);
    setDescription(task.description ?? "");
    setProjectId(task.projectId ?? "");
    setDueDate(task.dueDate ?? "");
    setEditing(true);
  }

  async function save() {
    const trimmed = title.trim();
    if (!trimmed || saving) return;
    setSaving(true);
    try {
      const updated = await persistTaskUpdate({
        taskId: task.id,
        title: trimmed,
        description: description.trim() || undefined,
        projectId: projectId || undefined,
        dueDate: dueDate || undefined,
        // The edit form doesn't touch the checklist - carry it through
        // unchanged, since PATCH /tasks/{id} is a full replace.
        checklist: task.checklist,
      });
      updateTask(task.id, {
        title: updated.title,
        description: updated.description,
        projectId: updated.projectId,
        dueDate: updated.dueDate,
        checklist: updated.checklist,
      });
      setEditing(false);
    } catch (error) {
      console.error("Could not update task:", error);
      toast.error("Couldn't save task", {
        description: "Nothing was saved. Check the connection and try again.",
      });
    } finally {
      setSaving(false);
    }
  }

  // Checklist edits happen straight from view mode (no separate edit step,
  // like Trello) - optimistic update first for instant checkbox feedback,
  // then persist; roll back and toast if the server rejects it.
  async function persistChecklist(next: ChecklistItem[]) {
    const previous = task.checklist;
    updateTask(task.id, { checklist: next });
    try {
      await persistTaskUpdate({
        taskId: task.id,
        title: task.title,
        description: task.description,
        projectId: task.projectId,
        dueDate: task.dueDate,
        checklist: next,
      });
    } catch (error) {
      console.error("Could not update checklist:", error);
      updateTask(task.id, { checklist: previous });
      toast.error("Couldn't update checklist", {
        description: "Nothing was saved. Check the connection and try again.",
      });
    }
  }

  function toggleChecklistItem(index: number) {
    persistChecklist(
      task.checklist.map((item, i) =>
        i === index ? { ...item, checked: !item.checked } : item,
      ),
    );
  }

  function removeChecklistItem(index: number) {
    persistChecklist(task.checklist.filter((_, i) => i !== index));
  }

  function addChecklistItem() {
    const text = newItemText.trim();
    if (!text) return;
    setNewItemText("");
    persistChecklist([...task.checklist, { text, checked: false }]);
  }

  async function logTime() {
    const minutes = Math.round(Number(minutesInput));
    if (!Number.isFinite(minutes) || minutes < 1) return;
    setLoggingTime(true);
    try {
      await logWorkBlock({ taskId: task.id, minutes });
      toast.success(`Logged ${minutes} min`, { description: task.title });
      setMinutesInput("");
      setTotalMinutes((current) => (current ?? 0) + minutes);
    } catch (error) {
      console.error("Could not log work block:", error);
      toast.error("Couldn't log time", { description: "Try again." });
    } finally {
      setLoggingTime(false);
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
              <DialogTitle>Edit task</DialogTitle>
            </DialogHeader>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="task-title"
                className="text-xs font-medium text-muted-foreground"
              >
                Title
              </label>
              <Input
                id="task-title"
                autoFocus
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="task-description"
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
                id="task-description"
                ref={descriptionRef}
                value={description}
                placeholder="Add a description…"
                className="min-h-32 rounded-t-none border-t-0"
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="task-project"
                  className="text-xs font-medium text-muted-foreground"
                >
                  Project <span className="font-normal">(optional)</span>
                </label>
                <NativeSelect
                  id="task-project"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                >
                  <option value="">No project</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="task-due-date"
                  className="text-xs font-medium text-muted-foreground"
                >
                  Due date <span className="font-normal">(optional)</span>
                </label>
                <Input
                  id="task-due-date"
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                />
              </div>
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
              <Button type="submit" disabled={!title.trim() || saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </DialogFooter>
          </form>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle className="pr-0 leading-snug sm:pr-32">
                {task.title}
              </DialogTitle>
            </DialogHeader>
            <div className="relative flex justify-end gap-1 sm:absolute sm:top-2 sm:right-10">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={startEditing}
              >
                <Pencil />
                <span className="sr-only">Edit task</span>
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => {
                  onOpenChange(false);
                  archiveTaskWithUndo(task);
                }}
              >
                <Archive />
                <span className="sr-only">Archive task</span>
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                onClick={() => setConfirmingDelete(true)}
              >
                <Trash2 />
                <span className="sr-only">Delete task</span>
              </Button>
            </div>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              {columnTitle && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    Status
                  </span>
                  <Badge variant="secondary" className="rounded-full">
                    {columnTitle}
                  </Badge>
                </div>
              )}
              {project && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    Project
                  </span>
                  <Badge variant="secondary" className="rounded-full">
                    {project.name}
                  </Badge>
                </div>
              )}
              {task.dueDate && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    Due
                  </span>
                  <Badge
                    variant={
                      isOverdue(task.dueDate, columnId) ? "destructive" : "secondary"
                    }
                    className="rounded-full"
                  >
                    {formatDueDate(task.dueDate)}
                  </Badge>
                </div>
              )}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-muted-foreground">
                  Time spent
                </span>
                <Badge variant="secondary" className="rounded-full">
                  {totalMinutes === null ? "…" : formatMinutes(totalMinutes)}
                </Badge>
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                Description
              </span>
              {task.description ? (
                <MarkdownText text={task.description} />
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No description
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <span className="text-xs font-medium text-muted-foreground">
                Checklist
                {task.checklist.length > 0 &&
                  ` (${task.checklist.filter((i) => i.checked).length}/${task.checklist.length})`}
              </span>
              {task.checklist.map((item, index) => (
                <label
                  key={index}
                  className="flex items-center gap-2 text-sm"
                >
                  <Checkbox
                    checked={item.checked}
                    onCheckedChange={() => toggleChecklistItem(index)}
                  />
                  <span
                    className={cn(
                      "flex-1",
                      item.checked && "text-muted-foreground line-through",
                    )}
                  >
                    {item.text}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Remove ${item.text}`}
                    className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    onClick={() => removeChecklistItem(index)}
                  >
                    <Trash2 />
                  </Button>
                </label>
              ))}
              <form
                className="flex items-center gap-1.5"
                onSubmit={(e) => {
                  e.preventDefault();
                  addChecklistItem();
                }}
              >
                <Input
                  value={newItemText}
                  placeholder="Add an item…"
                  onChange={(e) => setNewItemText(e.target.value)}
                />
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={!newItemText.trim()}
                >
                  <Plus /> Add
                </Button>
              </form>
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="log-minutes"
                className="text-xs font-medium text-muted-foreground"
              >
                Log time
              </label>
              <form
                className="flex items-center gap-2"
                onSubmit={(e) => {
                  e.preventDefault();
                  logTime();
                }}
              >
                <Input
                  id="log-minutes"
                  type="number"
                  min={1}
                  step={1}
                  inputMode="numeric"
                  placeholder="Minutes"
                  value={minutesInput}
                  onChange={(e) => setMinutesInput(e.target.value)}
                  className="w-24"
                />
                <Button
                  type="submit"
                  variant="outline"
                  size="sm"
                  disabled={loggingTime || !minutesInput}
                >
                  Add
                </Button>
              </form>
            </div>
          </>
        )}
      </DialogContent>
      <ConfirmDeleteDialog
        task={task}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
        onConfirm={() => onOpenChange(false)}
      />
    </Dialog>
  );
}
