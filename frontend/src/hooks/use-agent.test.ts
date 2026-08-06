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
  });
});
