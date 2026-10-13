"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Status = "idle" | "streaming" | "waiting" | "error";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Change {
  type: "create_task" | "move_task" | "update_task";
  title: string;
  column_id?: string;
  description?: string;
  project_id?: string;
  project_name?: string;
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

type SSEEvent = { event: string; data: unknown };

type StreamPayload = { message?: string; resume?: { approved: boolean } };

/**
 * Stable conversation id. CLAUDE.md specifies thread_id = board id (one
 * conversation per board); there is a single board per user, so a constant
 * works, and the backend namespaces it per user. It is a UUID so it also
 * satisfies a backend that validates the id's shape.
 */
export const BOARD_THREAD_ID = "00000000-0000-4000-8000-000000000001";

/** Parse one SSE event block (the text between blank lines). */
function parseSSEBlock(block: string): SSEEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  const dataText = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(dataText) };
  } catch {
    return { event, data: dataText };
  }
}

/**
 * Read an SSE body incrementally, calling `onEvent` for each complete event as
 * soon as it arrives. Partial lines/events are buffered across chunks.
 */
export async function readSSE(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const flush = (final: boolean) => {
    buffer = buffer.replace(/\r\n?/g, "\n");
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const parsed = parseSSEBlock(block);
      if (parsed && !signal?.aborted) onEvent(parsed);
    }
    if (final && buffer.trim()) {
      const parsed = parseSSEBlock(buffer);
      buffer = "";
      if (parsed && !signal?.aborted) onEvent(parsed);
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      flush(false);
    }
    buffer += decoder.decode();
    flush(true);
  } finally {
    reader.releaseLock();
  }
}

/** Build a readable message from a non-ok response, preferring FastAPI's `detail`. */
async function errorFromResponse(res: Response): Promise<string> {
  const fallback = `Request failed (${res.status}${res.statusText ? ` ${res.statusText}` : ""})`;
  try {
    const { detail } = (await res.json()) as { detail?: unknown };
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      const msgs = detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : ""))
        .filter(Boolean);
      if (msgs.length > 0) return msgs.join("; ");
    }
  } catch {
    // Not JSON - use the fallback.
  }
  return fallback;
}

function isAbortError(err: unknown): boolean {
  return (
    typeof err === "object" &&
    err !== null &&
    "name" in err &&
    (err as { name: unknown }).name === "AbortError"
  );
}

function postStream(threadId: string, payload: StreamPayload, signal: AbortSignal) {
  return fetch("/agent/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ thread_id: threadId, ...payload }),
    signal,
  });
}

export function useAgent({ onApply }: UseAgentOptions = {}) {
  const [status, setStatus] = useState<Status>("idle");
  const [messages, setMessages] = useState<Message[]>([]);
  const [pendingDiff, setPendingDiff] = useState<PendingDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const threadId = BOARD_THREAD_ID;

  const sawInterruptRef = useRef(false);
  const sawErrorRef = useRef(false);
  const sawTerminalRef = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  // Cancel any in-flight request when the component using the hook unmounts.
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const handleEvent = useCallback(
    ({ event, data }: SSEEvent) => {
      if (event === "interrupt") {
        sawInterruptRef.current = true;
        sawTerminalRef.current = true;
        setPendingDiff(data as PendingDiff);
        setStatus("waiting");
      } else if (event === "message") {
        const msg = data as { role: string; content: string };
        if (msg.role === "assistant" && msg.content) {
          setMessages((prev) => [...prev, { role: "assistant", content: msg.content }]);
        }
      } else if (event === "apply") {
        const {
          created_tasks: created = [],
          moved_tasks: moved = [],
          updated_tasks: updated = [],
        } = data as {
          created_tasks?: AppliedTask[];
          moved_tasks?: AppliedTask[];
          updated_tasks?: AppliedTask[];
        };
        onApply?.([...created, ...moved, ...updated]);
        sawInterruptRef.current = false;
        sawTerminalRef.current = true;
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
        if (updated.length > 0) {
          parts.push(`Updated: ${formatTasks(updated)}`);
        }
        const content = parts.length > 0 ? parts.join(". ") : "Changes cancelled.";
        setMessages((prev) => [...prev, { role: "assistant", content }]);
      } else if (event === "error") {
        const message = (data as { message?: string }).message ?? "Agent error";
        sawInterruptRef.current = false;
        sawErrorRef.current = true;
        sawTerminalRef.current = true;
        setError(message);
        setStatus("error");
      } else if (event === "done") {
        sawTerminalRef.current = true;
        // A trailing "done" must not override a pending diff or an error.
        if (!sawInterruptRef.current && !sawErrorRef.current) {
          setStatus("idle");
        }
      }
    },
    [onApply],
  );

  /**
   * POST to the agent stream and dispatch events as they arrive.
   * Returns false if the request failed before the stream was accepted.
   */
  const runStream = useCallback(
    async (payload: StreamPayload, onAccepted?: () => void): Promise<boolean> => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      sawInterruptRef.current = false;
      sawErrorRef.current = false;
      sawTerminalRef.current = false;
      setError(null);
      setStatus("streaming");

      let accepted = false;
      try {
        const res = await postStream(threadId, payload, controller.signal);
        if (!res.ok) {
          throw new Error(await errorFromResponse(res));
        }
        accepted = true;
        onAccepted?.();
        if (res.body) {
          await readSSE(res.body, handleEvent, controller.signal);
        }
        if (controller.signal.aborted) return true;
        if (!sawTerminalRef.current) {
          setError("The agent stream ended unexpectedly.");
          setStatus("error");
        }
        return true;
      } catch (err) {
        if (controller.signal.aborted || isAbortError(err)) return accepted;
        setError(err instanceof Error ? err.message : "Network error");
        setStatus("error");
        return accepted;
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
      }
    },
    [handleEvent, threadId],
  );

  const send = useCallback(
    async (content: string) => {
      setMessages((prev) => [...prev, { role: "user", content }]);
      await runStream({ message: content });
    },
    [runStream],
  );

  const resume = useCallback(
    async (approved: boolean) => {
      if (!pendingDiff) return;
      // Keep the diff until the backend accepts the resume, so a failed request
      // leaves it on screen and the user can retry (the thread is still interrupted).
      const accepted = await runStream({ resume: { approved } }, () => setPendingDiff(null));
      if (!accepted) {
        setStatus((prev) => (prev === "error" ? "waiting" : prev));
      }
    },
    [pendingDiff, runStream],
  );

  const approve = useCallback(() => resume(true), [resume]);
  const reject = useCallback(() => resume(false), [resume]);

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
