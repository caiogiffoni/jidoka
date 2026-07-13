"use client";

import { useEffect, useRef, useState } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { TaskDialog } from "./task-dialog";
import type { Task } from "@/lib/types";

export function TaskCard({ task, overlay }: { task: Task; overlay?: boolean }) {
  return (
    <Card
      className={cn(
        "cursor-grab gap-0 py-3 shadow-none transition-shadow duration-150 select-none hover:shadow-sm hover:ring-foreground/20",
        overlay && "cursor-grabbing rotate-2 shadow-lg ring-ring/40",
      )}
    >
      <CardContent className="px-3">
        <p className="text-sm leading-snug font-medium">{task.title}</p>
        {task.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {task.description}
          </p>
        )}
      </CardContent>
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
        <TaskCard task={task} />
      </div>
      <TaskDialog task={task} open={open} onOpenChange={setOpen} />
    </>
  );
}
