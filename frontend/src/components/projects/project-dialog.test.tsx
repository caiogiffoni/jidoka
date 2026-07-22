import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/app/actions", () => ({
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { toast } from "sonner";
import { updateProject } from "@/app/actions";
import { ProjectDialog } from "./project-dialog";
import type { Project } from "@/lib/types";

const project: Project = {
  id: "p1",
  name: "Alpha",
  description: "Original notes",
  createdAt: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(updateProject).mockReset().mockResolvedValue(project);
  vi.mocked(toast.error).mockClear();
});

it("opens in edit mode when initialMode is edit and saves the trimmed fields", async () => {
  const user = userEvent.setup();
  render(
    <ProjectDialog
      project={project}
      open
      onOpenChange={() => {}}
      initialMode="edit"
    />,
  );

  const dialog = within(await screen.findByRole("dialog"));
  const nameInput = dialog.getByLabelText("Name");
  expect(nameInput).toHaveValue("Alpha");

  await user.clear(nameInput);
  await user.type(nameInput, "  Alpha Renamed  ");
  await user.click(dialog.getByRole("button", { name: "Save" }));

  expect(updateProject).toHaveBeenCalledWith({
    id: "p1",
    name: "Alpha Renamed",
    description: "Original notes",
  });
});

it("renders the description as Markdown in view mode", async () => {
  render(<ProjectDialog project={project} open onOpenChange={() => {}} />);

  const dialog = within(await screen.findByRole("dialog"));
  expect(dialog.getByText("Original notes")).toBeInTheDocument();
  expect(dialog.queryByLabelText("Name")).not.toBeInTheDocument();
});

it("shows an error toast when saving fails", async () => {
  const user = userEvent.setup();
  vi.mocked(updateProject).mockRejectedValueOnce(new Error("network"));
  render(
    <ProjectDialog
      project={project}
      open
      onOpenChange={() => {}}
      initialMode="edit"
    />,
  );

  const dialog = within(await screen.findByRole("dialog"));
  await user.click(dialog.getByRole("button", { name: "Save" }));

  expect(toast.error).toHaveBeenCalled();
});
