"use client";

import { useRef, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { createProject } from "@/app/actions";

export function CreateProjectDialog() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dailyEnabled, setDailyEnabled] = useState(false);
  const [dailyTemplate, setDailyTemplate] = useState<string[]>([]);
  const itemRefs = useRef<(HTMLInputElement | null)[]>([]);

  function reset() {
    setName("");
    setDescription("");
    setDailyEnabled(false);
    setDailyTemplate([]);
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

  async function submit() {
    const trimmed = name.trim();
    if (!trimmed || pending) return;
    setPending(true);
    try {
      await createProject({
        name: trimmed,
        description: description.trim() || undefined,
        dailyEnabled,
        dailyTemplate: dailyTemplate.map((item) => item.trim()).filter(Boolean),
      });
      reset();
      setOpen(false);
    } catch (error) {
      console.error("Could not create project:", error);
      toast.error("Couldn't create project", {
        description: "Nothing was saved. Check the connection and try again.",
      });
    } finally {
      setPending(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus /> Add project
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add project</DialogTitle>
        </DialogHeader>
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="new-project-name"
              className="text-xs font-medium text-muted-foreground"
            >
              Name
            </label>
            <Input
              id="new-project-name"
              autoFocus
              value={name}
              placeholder="Project name…"
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="new-project-description"
              className="text-xs font-medium text-muted-foreground"
            >
              Description{" "}
              <span className="font-normal">(optional, Markdown supported)</span>
            </label>
            <Textarea
              id="new-project-description"
              value={description}
              placeholder="What is this project about…"
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
                  One card is created each day titled &ldquo;Daily - DD-MM-YY
                  - {name.trim() || "Project Name"}&rdquo;, with each line
                  below as a checklist item.
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
            <DialogClose asChild>
              <Button type="button" variant="outline">
                Cancel
              </Button>
            </DialogClose>
            <Button type="submit" disabled={!name.trim() || pending}>
              {pending ? "Adding…" : "Add project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
