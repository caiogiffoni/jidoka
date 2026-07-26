"use client";

import { useRef, useState } from "react";
import { Plus } from "lucide-react";
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
import type { DailyTemplate } from "@/lib/types";
import { DailyTemplateDialog } from "./daily-template-dialog";

export function CreateProjectDialog() {
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dailyEnabled, setDailyEnabled] = useState(false);
  const [dailyTemplate, setDailyTemplate] = useState<DailyTemplate | null>(null);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  // True only when the template popup closed via its own Save button - see
  // ProjectDialog for why a ref (rather than checking dailyTemplate directly
  // in the popup's onOpenChange) is what decides whether cancelling should
  // revert the checkbox.
  const savedTemplateRef = useRef(false);

  function reset() {
    setName("");
    setDescription("");
    setDailyEnabled(false);
    setDailyTemplate(null);
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
        dailyTemplate,
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
                onCheckedChange={(checked) => {
                  const next = checked === true;
                  setDailyEnabled(next);
                  if (next) setTemplateDialogOpen(true);
                }}
              />
              Generate a daily task
            </label>
            {dailyEnabled && (
              <div className="flex flex-col gap-1.5 pl-6">
                {dailyTemplate ? (
                  <div className="text-xs text-muted-foreground">
                    {dailyTemplate.title && (
                      <p className="font-medium text-foreground">
                        {dailyTemplate.title}
                      </p>
                    )}
                    {dailyTemplate.checklist.length > 0 && (
                      <ul className="list-inside list-disc">
                        {dailyTemplate.checklist.map((item, index) => (
                          <li key={index}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">
                    No template yet
                  </p>
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="self-start"
                  onClick={() => setTemplateDialogOpen(true)}
                >
                  Edit template
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
      <DailyTemplateDialog
        open={templateDialogOpen}
        onOpenChange={(next) => {
          setTemplateDialogOpen(next);
          if (!next) {
            if (!savedTemplateRef.current && dailyTemplate === null) {
              setDailyEnabled(false);
            }
            savedTemplateRef.current = false;
          }
        }}
        projectName={name}
        initialTemplate={dailyTemplate}
        onSave={(template) => {
          savedTemplateRef.current = true;
          setDailyTemplate(template);
        }}
      />
    </Dialog>
  );
}
