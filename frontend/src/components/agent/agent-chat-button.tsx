"use client";

import * as React from "react";
import { Bot } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ChatPanel } from "./chat-panel";

export function AgentChatButton() {
  const [open, setOpen] = React.useState(false);
  const router = useRouter();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Open agent chat"
        onClick={() => setOpen(true)}
      >
        <Bot />
      </Button>
      <ChatPanel
        open={open}
        onOpenChange={setOpen}
        onApply={() => {
          // Refresh server-fetched board data after the agent applies changes.
          router.refresh();
        }}
      />
    </>
  );
}
