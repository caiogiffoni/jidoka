"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { MarkdownText } from "@/components/ui/markdown-text";
import { useAgent } from "@/hooks/use-agent";

interface ChatPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApply?: (tasks: { id: string; title: string; column_id: string }[]) => void;
}

export function ChatPanel({ open, onOpenChange, onApply }: ChatPanelProps) {
  const { messages, pendingDiff, status, error, send, approve, reject } = useAgent({ onApply });
  const [input, setInput] = React.useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    send(trimmed);
    setInput("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Agent</DialogTitle>
        </DialogHeader>

        <div className="flex max-h-[80vh] flex-col gap-4">
          <div className="flex flex-col gap-2 overflow-y-auto">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`rounded-lg px-3 py-2 text-sm ${
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground self-end"
                    : "bg-muted self-start"
                }`}
              >
                <MarkdownText text={msg.content} />
              </div>
            ))}
          </div>

          {pendingDiff && (
            <div className="rounded-lg border bg-card p-3">
              <p className="text-sm font-medium">Proposed changes</p>
              <ul className="mt-2 space-y-2">
                {pendingDiff.changes.map((change, index) => (
                  <li key={index} className="text-sm">
                    <span className="font-medium">{change.title}</span>
                    <span className="text-muted-foreground ml-2">
                      {change.column_id}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex gap-2">
                <Button onClick={approve} size="sm">
                  Approve
                </Button>
                <Button onClick={reject} variant="outline" size="sm">
                  Reject
                </Button>
              </div>
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          <form onSubmit={handleSubmit} className="flex gap-2">
            <Input
              placeholder="Ask the agent..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={status === "streaming" || status === "waiting"}
            />
            <Button type="submit" disabled={status === "streaming" || status === "waiting"}>
              Send
            </Button>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}
