"use client";

import {
  Bold,
  HelpCircle,
  Italic,
  Link as LinkIcon,
  List,
  ListOrdered,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

interface Edit {
  next: string;
  selectionStart: number;
  selectionEnd: number;
}

function wrapSelection(
  textarea: HTMLTextAreaElement,
  value: string,
  before: string,
  after: string = before,
): Edit {
  const { selectionStart: start, selectionEnd: end } = textarea;
  const selected = value.slice(start, end);
  return {
    next: value.slice(0, start) + before + selected + after + value.slice(end),
    selectionStart: start + before.length,
    selectionEnd: start + before.length + selected.length,
  };
}

// Prefixes every line touched by the selection - e.g. turning a
// multi-line selection into a bulleted or numbered list in one go.
function prefixLines(
  textarea: HTMLTextAreaElement,
  value: string,
  prefix: (lineIndex: number) => string,
): Edit {
  const { selectionStart: start, selectionEnd: end } = textarea;
  const blockStart = value.lastIndexOf("\n", start - 1) + 1;
  const nextNewline = value.indexOf("\n", end);
  const blockEnd = nextNewline === -1 ? value.length : nextNewline;
  const prefixed = value
    .slice(blockStart, blockEnd)
    .split("\n")
    .map((line, i) => prefix(i) + line)
    .join("\n");
  return {
    next: value.slice(0, blockStart) + prefixed + value.slice(blockEnd),
    selectionStart: blockStart,
    selectionEnd: blockStart + prefixed.length,
  };
}

// A small formatting toolbar for a plain-text Markdown Textarea: buttons
// wrap/prefix the current selection with Markdown syntax rather than
// rendering rich text, since descriptions are stored and rendered as plain
// Markdown (see MarkdownText) - no WYSIWYG editor dependency needed.
export function MarkdownToolbar({
  textareaRef,
  value,
  onChange,
}: {
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (value: string) => void;
}) {
  function apply(edit: (textarea: HTMLTextAreaElement, value: string) => Edit) {
    const textarea = textareaRef.current;
    if (!textarea) return;
    const { next, selectionStart, selectionEnd } = edit(textarea, value);
    onChange(next);
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(selectionStart, selectionEnd);
    });
  }

  return (
    <div className="flex items-center gap-0.5 rounded-t-lg border border-b-0 border-input bg-muted/40 p-1 dark:bg-input/30">
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Bold"
        onClick={() => apply((ta, v) => wrapSelection(ta, v, "**"))}
      >
        <Bold />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Italic"
        onClick={() => apply((ta, v) => wrapSelection(ta, v, "*"))}
      >
        <Italic />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Bulleted list"
        onClick={() => apply((ta, v) => prefixLines(ta, v, () => "- "))}
      >
        <List />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Numbered list"
        onClick={() =>
          apply((ta, v) => prefixLines(ta, v, (i) => `${i + 1}. `))
        }
      >
        <ListOrdered />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label="Link"
        onClick={() => apply((ta, v) => wrapSelection(ta, v, "[", "](https://)"))}
      >
        <LinkIcon />
      </Button>
      <Popover>
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Formatting help"
            className="ml-auto"
          >
            <HelpCircle />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-56 text-xs">
          <p className="mb-1.5 font-medium">Formatting help</p>
          <ul className="space-y-1 font-mono text-muted-foreground">
            <li>**bold**</li>
            <li>*italic*</li>
            <li># heading</li>
            <li>- list item</li>
            <li>1. numbered item</li>
            <li>[text](url)</li>
            <li>--- (horizontal rule)</li>
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
