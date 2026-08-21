"use client";

import { useEffect, useRef, useState } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  CalendarClock,
  GripVertical,
  MoreVertical,
  SquareCheck,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { formatDueDate, isOverdue } from "@/lib/due-date";
import { archiveTaskWithUndo } from "./archive-task";
import { ConfirmDeleteDialog } from "./delete-task";
import { TaskDialog } from "./task-dialog";
import type { ColumnId, Project, Task } from "@/lib/types";

function readCoarsePointer(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(pointer: coarse)").matches;
}

function useCoarsePointer() {
  const [coarse, setCoarse] = useState(readCoarsePointer);
  useEffect(() => {
    const mql = window.matchMedia("(pointer: coarse)");
    const handler = (event: MediaQueryListEvent) => setCoarse(event.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);
  return coarse;
}

export function TaskCard({
  task,
  columnId,
  overlay,
  onArchive,
  onDelete,
  disabled = false,
}: {
  task: Task;
  columnId?: ColumnId;
  overlay?: boolean;
  onArchive?: () => void;
  onDelete?: () => void;
  disabled?: boolean;
}) {
  return (
    <Card
      className={cn(
        "group relative gap-0 py-3 shadow-none transition-shadow duration-150 select-none hover:shadow-sm hover:ring-foreground/20",
        !disabled && "cursor-grab",
        overlay && "cursor-grabbing rotate-2 shadow-lg ring-ring/40",
      )}
    >
      <CardContent className="px-3">
        <p
          className={cn(
            "text-sm leading-snug font-medium",
            (onArchive || onDelete) && "pr-5",
          )}
        >
          {task.title}
        </p>
        {task.description && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {task.description}
          </p>
        )}
        {(task.checklist.length > 0 || task.dueDate) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {task.checklist.length > 0 && (
              <span className="flex items-center gap-1">
                <SquareCheck className="size-3.5" />
                {task.checklist.filter((item) => item.checked).length}/
                {task.checklist.length}
              </span>
            )}
            {task.dueDate && (
              <span
                className={cn(
                  "flex items-center gap-1",
                  isOverdue(task.dueDate, columnId) &&
                    "rounded-full bg-destructive/10 px-1.5 text-destructive",
                )}
              >
                <CalendarClock className="size-3.5" />
                {formatDueDate(task.dueDate)}
              </span>
            )}
          </div>
        )}
      </CardContent>
      {(onArchive || onDelete) && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className={cn(
                "absolute top-1.5 right-1.5 flex size-6 items-center justify-center rounded-md text-muted-foreground",
                // Hidden until the card is hovered or the button is focused;
                // coarse pointers can't hover, so keep it available there.
                // When the menu is open the trigger stays visible even if the
                // pointer has moved over the dropdown content.
                "pointer-events-none opacity-0 transition-opacity duration-150",
                "group-hover:pointer-events-auto group-hover:opacity-100",
                "focus-visible:pointer-events-auto focus-visible:opacity-100",
                "pointer-coarse:pointer-events-auto pointer-coarse:opacity-100",
                "data-[state=open]:pointer-events-auto data-[state=open]:opacity-100",
                "hover:bg-accent hover:text-foreground active:translate-y-px",
                "outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
              )}
              // The card is a dnd-kit draggable and opens the dialog on click:
              // keep pointer, click, and key events on this button from reaching it.
              onPointerDown={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") e.stopPropagation();
              }}
            >
              <MoreVertical className="size-3.5" />
              <span className="sr-only">Task actions</span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {onArchive && (
              <DropdownMenuItem onClick={onArchive}>Archive</DropdownMenuItem>
            )}
            {onDelete && (
              <DropdownMenuItem variant="destructive" onClick={onDelete}>
                Delete
              </DropdownMenuItem>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </Card>
  );
}

export function SortableTaskCard({
  task,
  columnId,
  projects,
  disabled = false,
}: {
  task: Task;
  columnId: ColumnId;
  projects: Project[];
  disabled?: boolean;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: task.id, disabled });
  const [open, setOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const coarse = useCoarsePointer();
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

  // On touch devices the board itself is a horizontal scroll container, so a
  // full-card drag gesture conflicts with scrolling. Use a dedicated drag
  // handle on coarse pointers and keep the desktop "grab anywhere" behavior.
  const wrapperListeners = coarse ? undefined : listeners;
  const wrapperAttributes = coarse ? undefined : attributes;

  return (
    <>
      <div
        ref={setNodeRef}
        style={{ transform: CSS.Transform.toString(transform), transition }}
        className={cn(
          "relative m-0.5 touch-manipulation rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
          coarse && "pl-6",
          isDragging &&
            "border border-dashed border-muted-foreground/30 bg-muted/60 *:invisible",
        )}
        onClick={handleClick}
        {...wrapperAttributes}
        {...wrapperListeners}
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
        {coarse && (
          <div
            {...attributes}
            {...listeners}
            className="absolute top-1/2 left-1 z-10 -translate-y-1/2 touch-none rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground active:bg-accent"
            onClick={(event) => event.stopPropagation()}
          >
            <GripVertical className="size-4" />
            <span className="sr-only">Drag task</span>
          </div>
        )}
        <TaskCard
          task={task}
          columnId={columnId}
          onArchive={() => archiveTaskWithUndo(task)}
          onDelete={() => setConfirmingDelete(true)}
          disabled={disabled}
        />
      </div>
      <TaskDialog
        task={task}
        projects={projects}
        open={open}
        onOpenChange={setOpen}
      />
      <ConfirmDeleteDialog
        task={task}
        open={confirmingDelete}
        onOpenChange={setConfirmingDelete}
      />
    </>
  );
}
