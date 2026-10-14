import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAgent } from "./use-agent";

const originalFetch = global.fetch;

function makeStream(events: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(event));
      }
      controller.close();
    },
  });
}

describe("useAgent", () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("starts idle with no messages or diffs", () => {
    const { result } = renderHook(() => useAgent());
    expect(result.current.status).toBe("idle");
    expect(result.current.messages).toEqual([]);
    expect(result.current.pendingDiff).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("sends a user message and transitions to streaming", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(makeStream(["event: done\ndata: {}\n\n"]), {
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task");
    });

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/agent/stream"),
      expect.objectContaining({
        method: "POST",
        body: expect.stringContaining("Add a task"),
      }),
    );
    expect(result.current.messages).toContainEqual(
      expect.objectContaining({ role: "user", content: "Add a task" }),
    );
  });

  it("appends assistant messages from the stream", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(
        makeStream([
          'event: message\ndata: {"role":"assistant","content":"Hello"}\n\n',
          "event: done\ndata: {}\n\n",
        ]),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Hi");
    });

    expect(result.current.messages).toContainEqual(
      expect.objectContaining({ role: "assistant", content: "Hello" }),
    );
    expect(result.current.status).toBe("idle");
  });

  it("shows a pending diff when the stream emits an interrupt event", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(
        makeStream([
          'event: interrupt\ndata: {"changes":[{"type":"create_task","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
          "event: done\ndata: {}\n\n",
        ]),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task to wire HITL");
    });

    await waitFor(() => {
      expect(result.current.status).toBe("waiting");
    });

    expect(result.current.pendingDiff).toEqual({
      changes: [
        expect.objectContaining({
          type: "create_task",
          title: "Wire HITL flow",
          column_id: "todo",
        }),
      ],
    });
  });

  it("approves a diff and surfaces applied tasks", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"create_task","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: apply\ndata: {"created_tasks":[{"id":"t1","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      );

    const onApply = vi.fn();
    const { result } = renderHook(() => useAgent({ onApply }));

    await act(async () => {
      await result.current.send("Add a task");
    });

    await waitFor(() => expect(result.current.status).toBe("waiting"));

    await act(async () => {
      await result.current.approve();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("idle");
    });

    expect(onApply).toHaveBeenCalledWith([
      expect.objectContaining({ id: "t1", title: "Wire HITL flow" }),
    ]);
    expect(result.current.pendingDiff).toBeNull();
    expect(result.current.messages).toContainEqual(
      expect.objectContaining({ role: "assistant", content: "Created: Wire HITL flow" }),
    );
  });

  it("rejects a diff without applying", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"create_task","title":"Rejected task"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: apply\ndata: {"created_tasks":[]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      );

    const onApply = vi.fn();
    const { result } = renderHook(() => useAgent({ onApply }));

    await act(async () => {
      await result.current.send("Add a task");
    });

    await waitFor(() => expect(result.current.status).toBe("waiting"));

    await act(async () => {
      await result.current.reject();
    });

    expect(global.fetch).toHaveBeenLastCalledWith(
      expect.any(String),
      expect.objectContaining({
        body: expect.stringContaining('"approved":false'),
      }),
    );
    expect(onApply).toHaveBeenCalledWith([]);
    expect(result.current.pendingDiff).toBeNull();
    expect(result.current.messages).toContainEqual(
      expect.objectContaining({ role: "assistant", content: "Changes cancelled." }),
    );
  });

  it("approves a diff with multiple moved tasks and surfaces their titles", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"move_task","title":"Wire HITL flow","from_column_id":"todo","to_column_id":"done"},{"type":"move_task","title":"Read docs","from_column_id":"todo","to_column_id":"done"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: apply\ndata: {"created_tasks":[],"moved_tasks":[{"id":"t1","title":"Wire HITL flow","column_id":"done"},{"id":"t2","title":"Read docs","column_id":"done"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      );

    const onApply = vi.fn();
    const { result } = renderHook(() => useAgent({ onApply }));

    await act(async () => {
      await result.current.send("Move everything to done");
    });

    await waitFor(() => expect(result.current.status).toBe("waiting"));

    await act(async () => {
      await result.current.approve();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("idle");
    });

    expect(onApply).toHaveBeenCalledWith([
      expect.objectContaining({ id: "t1", title: "Wire HITL flow" }),
      expect.objectContaining({ id: "t2", title: "Read docs" }),
    ]);
    expect(result.current.messages).toContainEqual(
      expect.objectContaining({
        role: "assistant",
        content: "Moved: Wire HITL flow, Read docs",
      }),
    );
  });

  it("approves an update diff and surfaces updated task titles", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"update_task","title":"Wire HITL flow","task_id":"t1"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: apply\ndata: {"created_tasks":[],"moved_tasks":[],"updated_tasks":[{"id":"t1","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      );

    const onApply = vi.fn();
    const { result } = renderHook(() => useAgent({ onApply }));

    await act(async () => {
      await result.current.send("Update the description");
    });

    await waitFor(() => expect(result.current.status).toBe("waiting"));

    await act(async () => {
      await result.current.approve();
    });

    await waitFor(() => {
      expect(result.current.status).toBe("idle");
    });

    expect(onApply).toHaveBeenCalledWith([
      expect.objectContaining({ id: "t1", title: "Wire HITL flow" }),
    ]);
    expect(result.current.messages).toContainEqual(
      expect.objectContaining({
        role: "assistant",
        content: "Updated: Wire HITL flow",
      }),
    );
  });

  it("surfaces an error when the stream emits an error event", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(
        makeStream([
          'event: error\ndata: {"message":"LLM failed"}\n\n',
          "event: done\ndata: {}\n\n",
        ]),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task");
    });

    await waitFor(() => {
      expect(result.current.error).toBe("LLM failed");
    });
    // The trailing "done" must not flip the status back to idle.
    expect(result.current.status).toBe("error");
  });

  it("dispatches events split across chunk boundaries", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(
        makeStream([
          "event: mess",
          'age\ndata: {"role":"assistant","con',
          'tent":"Hello"}\n',
          "\nevent: done\ndata: {}\n",
          "\n",
        ]),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Hi");
    });

    expect(result.current.messages).toContainEqual(
      expect.objectContaining({ role: "assistant", content: "Hello" }),
    );
    expect(result.current.status).toBe("idle");
  });

  it("dispatches events as they arrive, before the stream ends", async () => {
    const encoder = new TextEncoder();
    let controller!: ReadableStreamDefaultController<Uint8Array>;
    const body = new ReadableStream<Uint8Array>({
      start(c) {
        controller = c;
      },
    });
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(body, { headers: { "content-type": "text/event-stream" } }),
    );

    const { result } = renderHook(() => useAgent());

    let sendPromise!: Promise<void>;
    act(() => {
      sendPromise = result.current.send("Hi");
    });

    controller.enqueue(
      encoder.encode('event: message\ndata: {"role":"assistant","content":"Thinking"}\n\n'),
    );

    await waitFor(() => {
      expect(result.current.messages).toContainEqual(
        expect.objectContaining({ role: "assistant", content: "Thinking" }),
      );
    });
    expect(result.current.status).toBe("streaming");

    await act(async () => {
      controller.enqueue(encoder.encode("event: done\ndata: {}\n\n"));
      controller.close();
      await sendPromise;
    });

    expect(result.current.status).toBe("idle");
  });

  it("surfaces the FastAPI detail and sets error status on a non-ok response", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Rate limit exceeded" }), {
        status: 429,
        headers: { "content-type": "application/json" },
      }),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toBe("Rate limit exceeded");
  });

  it("falls back to the HTTP status when a non-ok response has no detail", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response("oops", { status: 500, statusText: "Internal Server Error" }),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toContain("500");
  });

  it("leaves streaming status when the stream ends without a terminal event", async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce(
      new Response(
        makeStream(['event: message\ndata: {"role":"assistant","content":"Partial"}\n\n']),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Hi");
    });

    expect(result.current.status).toBe("error");
    expect(result.current.error).toMatch(/ended unexpectedly/i);
  });

  it("keeps the pending diff when the approve request fails, so it can be retried", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"create_task","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: apply\ndata: {"created_tasks":[{"id":"t1","title":"Wire HITL flow","column_id":"todo"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      );

    const onApply = vi.fn();
    const { result } = renderHook(() => useAgent({ onApply }));

    await act(async () => {
      await result.current.send("Add a task");
    });
    await waitFor(() => expect(result.current.status).toBe("waiting"));

    await act(async () => {
      await result.current.approve();
    });

    expect(result.current.error).toBe("Failed to fetch");
    expect(result.current.pendingDiff).toEqual({
      changes: [expect.objectContaining({ title: "Wire HITL flow" })],
    });
    expect(result.current.status).toBe("waiting");
    expect(onApply).not.toHaveBeenCalled();

    // Retry succeeds.
    await act(async () => {
      await result.current.approve();
    });

    expect(result.current.pendingDiff).toBeNull();
    expect(result.current.status).toBe("idle");
    expect(result.current.error).toBeNull();
    expect(onApply).toHaveBeenCalledTimes(1);
  });

  it("keeps the pending diff when the reject request gets a non-ok response", async () => {
    vi.mocked(global.fetch)
      .mockResolvedValueOnce(
        new Response(
          makeStream([
            'event: interrupt\ndata: {"changes":[{"type":"create_task","title":"Keep me"}]}\n\n',
            "event: done\ndata: {}\n\n",
          ]),
          { headers: { "content-type": "text/event-stream" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Server exploded" }), { status: 500 }),
      );

    const { result } = renderHook(() => useAgent());

    await act(async () => {
      await result.current.send("Add a task");
    });
    await act(async () => {
      await result.current.reject();
    });

    expect(result.current.error).toBe("Server exploded");
    expect(result.current.pendingDiff).not.toBeNull();
  });

  it("aborts the in-flight request on unmount without setting an error", async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.mocked(global.fetch).mockImplementationOnce((_url, init) => {
      capturedSignal = init?.signal ?? undefined;
      return new Promise((_resolve, reject) => {
        capturedSignal?.addEventListener("abort", () => {
          reject(new DOMException("The operation was aborted.", "AbortError"));
        });
      });
    });

    const { result, unmount } = renderHook(() => useAgent());

    let sendPromise!: Promise<void>;
    act(() => {
      sendPromise = result.current.send("Hi");
    });
    expect(result.current.status).toBe("streaming");

    unmount();
    await sendPromise;

    expect(capturedSignal?.aborted).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it("uses the same thread id across mounts", async () => {
    vi.mocked(global.fetch).mockImplementation(async () =>
      new Response(makeStream(["event: done\ndata: {}\n\n"]), {
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const first = renderHook(() => useAgent());
    await act(async () => {
      await first.result.current.send("one");
    });
    first.unmount();

    const second = renderHook(() => useAgent());
    await act(async () => {
      await second.result.current.send("two");
    });

    const threadIds = vi
      .mocked(global.fetch)
      .mock.calls.map(([, init]) => JSON.parse(String(init?.body)).thread_id);
    expect(threadIds).toHaveLength(2);
    expect(threadIds[0]).toBe(threadIds[1]);
  });
});
