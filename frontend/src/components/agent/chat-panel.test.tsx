import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/hooks/use-agent", () => ({
  useAgent: vi.fn(),
}));

import { useAgent } from "@/hooks/use-agent";
import { ChatPanel } from "./chat-panel";

const mockUseAgent = vi.mocked(useAgent);

describe("ChatPanel", () => {
  beforeEach(() => {
    mockUseAgent.mockReturnValue({
      messages: [],
      pendingDiff: null,
      status: "idle",
      error: null,
      send: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
    });
  });

  it("renders an input and send button", () => {
    render(<ChatPanel open onOpenChange={() => {}} />);
    expect(screen.getByPlaceholderText(/ask the agent/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("sends the message when the form is submitted", async () => {
    const send = vi.fn();
    mockUseAgent.mockReturnValue({
      messages: [],
      pendingDiff: null,
      status: "idle",
      error: null,
      send,
      approve: vi.fn(),
      reject: vi.fn(),
    });

    const user = userEvent.setup();
    render(<ChatPanel open onOpenChange={() => {}} />);

    await user.type(screen.getByPlaceholderText(/ask the agent/i), "Add a task");
    await user.click(screen.getByRole("button", { name: /send/i }));

    expect(send).toHaveBeenCalledWith("Add a task");
  });

  it("renders a proposed diff with approve and reject buttons", async () => {
    mockUseAgent.mockReturnValue({
      messages: [
        { role: "user", content: "Add a task" },
        { role: "assistant", content: "I'll create that task." },
      ],
      pendingDiff: {
        changes: [
          {
            type: "create_task",
            title: "Wire HITL flow",
            column_id: "todo",
            description: undefined,
            project_id: undefined,
            checklist: [],
          },
        ],
      },
      status: "waiting",
      error: null,
      send: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
    });

    render(<ChatPanel open onOpenChange={() => {}} />);

    expect(screen.getByText("Wire HITL flow")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("calls approve when the approve button is clicked", async () => {
    const approve = vi.fn();
    mockUseAgent.mockReturnValue({
      messages: [],
      pendingDiff: {
        changes: [{ type: "create_task", title: "Wire HITL flow", column_id: "todo" }],
      },
      status: "waiting",
      error: null,
      send: vi.fn(),
      approve,
      reject: vi.fn(),
    });

    const user = userEvent.setup();
    render(<ChatPanel open onOpenChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: /approve/i }));
    expect(approve).toHaveBeenCalled();
  });

  it("displays an error message when the hook reports an error", () => {
    mockUseAgent.mockReturnValue({
      messages: [],
      pendingDiff: null,
      status: "idle",
      error: "LLM failed",
      send: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn(),
    });

    render(<ChatPanel open onOpenChange={() => {}} />);
    expect(screen.getByText("LLM failed")).toBeInTheDocument();
  });
});
