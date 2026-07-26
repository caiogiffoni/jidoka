"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import type { DailyTemplate } from "@/lib/types";
import { DailyTemplateDialog } from "./daily-template-dialog";

// The "Generate a daily task" checkbox + template preview + edit popup,
// shared by CreateProjectDialog and ProjectDialog's edit form - previously
// duplicated between the two verbatim. dailyEnabled/dailyTemplate stay
// lifted in the parent (it needs them at submit time); this component only
// owns the popup's own open state and the save-vs-cancel tracking ref.
export function DailyTemplateField({
  projectName,
  dailyEnabled,
  onDailyEnabledChange,
  dailyTemplate,
  onDailyTemplateChange,
}: {
  projectName: string;
  dailyEnabled: boolean;
  onDailyEnabledChange: (enabled: boolean) => void;
  dailyTemplate: DailyTemplate | null;
  onDailyTemplateChange: (template: DailyTemplate) => void;
}) {
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  // True only when the template popup closed via its own Save button - lets
  // the popup's onOpenChange tell a real save apart from a cancel/dismiss,
  // so "enable, then cancel with nothing saved yet" can revert the checkbox
  // without also reverting a just-saved (possibly empty) template.
  const savedTemplateRef = useRef(false);

  return (
    <div className="flex flex-col gap-2 rounded-md border p-3">
      <label className="flex items-center gap-2 text-sm font-medium">
        <Checkbox
          checked={dailyEnabled}
          onCheckedChange={(checked) => {
            const next = checked === true;
            onDailyEnabledChange(next);
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
      <DailyTemplateDialog
        open={templateDialogOpen}
        onOpenChange={(next) => {
          setTemplateDialogOpen(next);
          if (!next) {
            if (!savedTemplateRef.current && dailyTemplate === null) {
              onDailyEnabledChange(false);
            }
            savedTemplateRef.current = false;
          }
        }}
        projectName={projectName}
        initialTemplate={dailyTemplate}
        onSave={(template) => {
          savedTemplateRef.current = true;
          onDailyTemplateChange(template);
        }}
      />
    </div>
  );
}
