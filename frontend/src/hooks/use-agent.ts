"use client";

import { useCallback, useRef, useState } from "react";

type Status = "idle" | "streaming" | "waiting" | "error";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Change {
  type: "create_task" | "move_task";
  title: string;
  column_id?: string;
  description?: string;
  project_id?: string;
  checklist?: { text: string; checked: boolean }[];
  from_column_id?: string;
  to_column_id?: string;
  task_id?: string;
}

interface PendingDiff {
  changes: Change[];
}

interface AppliedTask {
  id: string;
  title: string;
  column_id: string;
}

interface UseAgentOptions {
  onApply?: (tasks: AppliedTask[]) => void;
}

function parseSSE(raw: string): { event: string; data: unknown }[] {
  const events: { event: string; data: unknown }[] = [];
  const blocks = raw.trim().split("\n\n");
  for (const block of blocks) {
    let event = "message";
    let dataText = "";
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataText += line.slice(5).trim();
      }
    }
    if (dataText) {
      try {
        events.push({ event, data: JSON.parse(dataText) });
      } catch {
        events.push({ event, data: dataText });
      }
    }
  }
  return events;
}

async function postStream(
  threadId: string,
  payload: { message?: string; resume?: { approved: boolean } },
) {
  const res = await fetch("/agent/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ thread_id: threadId, ...payload }),
  });
  return res;
}

export function useAgent({ onApply }: UseAgentOptions = {}) {
  const [status, setStatus] = useState<Status>("idle");
  const sawInterruptRef = useRef(false);

  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingDiff, setPendingDiff] = useState<PendingDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [threadId] = useState(() => crypto.randomUUID());

  const handleEvents = useCallback(
    (events: { event: string; data: unknown }[]) => {
      for (const { event, data } of events) {
        if (event === "interrupt") {
          const diff = data as PendingDiff;
          sawInterruptRef.current = true;
          setPendingDiff(diff);
          setStatus("waiting");
        } else if (event === "message") {
          const msg = data as { role: string; content: string };
          if (msg.role === "assistant" && msg.content) {
            setMessages((prev) => [...prev, { role: "assistant", content: msg.content }]);
          }
        } else if (event === "apply") {
          const { created_tasks: created = [], moved_tasks: moved = [] } = data as {
            created_tasks?: AppliedTask[];
            moved_tasks?: AppliedTask[];
          };
          onApply?.([...created, ...moved]);
          sawInterruptRef.current = false;
          setPendingDiff(null);
          setStatus("idle");
          const formatTasks = (tasks: AppliedTask[]) =>
            tasks
              .map((t) => t.title || `task ${t.id.slice(0, 8)}`)
              .filter(Boolean)
              .join(", ") || `${tasks.length} task(s)`;

          const parts: string[] = [];
          if (created.length > 0) {
            parts.push(`Created: ${formatTasks(created)}`);
          }
          if (moved.length > 0) {
            parts.push(`Moved: ${formatTasks(moved)}`);
          }
          const content = parts.length > 0 ? parts.join(". ") : "Changes cancelled.";
          setMessages((prev) => [...prev, { role: "assistant", content: content }]);
        } else if (event === "error") {
          const message = (data as { message?: string }).message ?? "Agent error";
          sawInterruptRef.current = false;
          setError(message);
          setStatus("error");
        } else if (event === "done") {
          if (!sawInterruptRef.current) {
            setStatus("idle");
          }
        }
      }
    },
    [onApply],
  );

  const send = useCallback(
    async (content: string) => {
      sawInterruptRef.current = false;
      setMessages((prev) => [...prev, { role: "user", content }]);
      setError(null);
      setStatus("streaming");

      try {
        const res = await postStream(threadId, { message: content });
        const text = await res.text();
        handleEvents(parseSSE(text));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Network error");
        setStatus("error");
      }
    },
    [handleEvents, threadId],
  );

  const approve = useCallback(async () => {
    if (!pendingDiff) return;
    sawInterruptRef.current = false;
    setStatus("streaming");
    setPendingDiff(null);
    try {
      const res = await postStream(threadId, { resume: { approved: true } });
      const text = await res.text();
      handleEvents(parseSSE(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
      setStatus("error");
    }
  }, [handleEvents, pendingDiff, threadId]);

  const reject = useCallback(async () => {
    if (!pendingDiff) return;
    sawInterruptRef.current = false;
    setPendingDiff(null);
    setStatus("streaming");
    try {
      const res = await postStream(threadId, { resume: { approved: false } });
      const text = await res.text();
      handleEvents(parseSSE(text));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
      setStatus("error");
    }
  }, [handleEvents, pendingDiff, threadId]);

  return {
    status,
    messages,
    pendingDiff,
    error,
    send,
    approve,
    reject,
  };
}
