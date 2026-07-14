"use client";

import { useEffect, useRef, useState } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ConfirmDeleteDialog } from "./delete-task";
import { TaskDialog } from "./task-dialog";
import type { Task } from "@/lib/types";

export function TaskCard({
  task,
  overlay,
  onDelete,
}: {
  task: Task;
  overlay?: boolean;
  onDelete?: () => void;
}) {
  return (
    <Card
      className={cn(
        "group relative cursor-grab gap-0 py-3 shadow-none transition-shadow duration-150 select-none hover:shadow-sm hover:ring-foreground/20",
        overlay && "cursor-grabbing rotate-2 shadow-lg ring-ring/40",
      )}
    >
      <CardContent className="px-3">
        <p
          className={cn(
            "text-sm leading-snug font-medium",
            onDelete && "pr-5",
          )}
        >
          {task.title}
        </p>
        {task.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {task.description}
          </p>
        )}
      </CardContent>
      {onDelete && (
        <button
          type="button"
          className={cn(
            "absolute top-1.5 right-1.5 flex size-6 items-center justify-center rounded-md text-muted-foreground",
            // Hidden until the card is hovered or the button is focused;
            // coarse pointers can't hover, so keep it available there.
            "pointer-events-none opacity-0 transition-opacity duration-150",
            "group-hover:pointer-events-auto group-hover:opacity-100",
            "focus-visible:pointer-events-auto focus-visible:opacity-100",
            "pointer-coarse:pointer-events-auto pointer-coarse:opacity-100",
            "hover:bg-destructive/10 hover:text-destructive active:translate-y-px",
            "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          )}
          // The card is a dnd-kit draggable and opens the dialog on click:
          // keep pointer, click, and key events on this button from reaching it.
          onPointerDown={(e) => e.stopPropagation()}
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") e.stopPropagation();
          }}
        >
          <X className="size-3.5" />
          <span className="sr-only">Delete task</span>
        </button>
      )}
    </Card>
  );
}

export function SortableTaskCard({ task }: { task: Task }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id });
  const [open, setOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // dnd-kit still fires a click on the card after a pointer drag ends;
  // remember the drag so that click doesn't open the dialog. The flag clears
  // shortly after the drag ends - the post-drop click (if any) fires first -
  // so a keyboard drag doesn't swallow the next real click.
  const wasDragged = useRef(false);
  useEffect(() => {
    if (isDragging) {
      wasDragged.current = true;
      return;
    }
    const timer = setTimeout(() => {
      wasDragged.current = false;
    }, 150);
    return () => clearTimeout(timer);
  }, [isDragging]);

  function handleClick() {
    if (wasDragged.current) {
      wasDragged.current = false;
      return;
    }
    setOpen(true);
  }

  return (
    <>
      <div
        ref={setNodeRef}
        style={{ transform: CSS.Transform.toString(transform), transition }}
        className={cn(
          "m-0.5 touch-manipulation rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          isDragging &&
            "border border-dashed border-muted-foreground/30 bg-muted/60 *:invisible",
        )}
        onClick={handleClick}
        {...attributes}
        {...listeners}
        // Enter opens the task; Space is dnd-kit's lift/drop key. Everything
        // else falls through to the keyboard sensor's own handler.
        onKeyDown={(e) => {
          if (e.key === "Enter" && !isDragging) {
            e.preventDefault();
            setOpen(true);
            return;
          }
          listeners?.onKeyDown?.(e);
        }}
      >
        <TaskCard task={task} onDelete={() => setConfirmingDelete(true)} />
      </div>
      <TaskDialog task={task} open={open} onOpenChange={setOpen} />
      <ConfirmDeleteDialog
        task={task}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
      />
    </>
  );
}
