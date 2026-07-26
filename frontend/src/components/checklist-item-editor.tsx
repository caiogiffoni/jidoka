"use client";

import { useRef } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// A plain list of checklist item texts (add/remove rows) - shared by any
// place that drafts a checklist before it exists as real ChecklistItem rows
// (a new task's checklist, or a project's daily-task template).
export function ChecklistItemEditor({
  items,
  onChange,
  itemPlaceholder = "e.g. write a check-in message in Slack",
}: {
  items: string[];
  onChange: (items: string[]) => void;
  itemPlaceholder?: string;
}) {
  const itemRefs = useRef<(HTMLInputElement | null)[]>([]);

  function updateItem(index: number, value: string) {
    onChange(items.map((it, i) => (i === index ? value : it)));
  }

  function removeItem(index: number) {
    onChange(items.filter((_, i) => i !== index));
  }

  // Focus the newly added row so typing can continue right away - without
  // this, focus stays on the "Add item" button and a space in what you type
  // next re-clicks it (native button behavior), silently adding blank rows.
  function addItem() {
    onChange([...items, ""]);
    requestAnimationFrame(() => {
      itemRefs.current[itemRefs.current.length - 1]?.focus();
    });
  }

  return (
    <div className="flex flex-col gap-1.5">
      {items.map((item, index) => (
        <div key={index} className="flex items-center gap-1.5">
          <Input
            ref={(el) => {
              itemRefs.current[index] = el;
            }}
            value={item}
            placeholder={itemPlaceholder}
            onChange={(e) => updateItem(index, e.target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Remove item"
            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            onClick={() => removeItem(index)}
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
        onClick={addItem}
      >
        <Plus /> Add item
      </Button>
    </div>
  );
}
