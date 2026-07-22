import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/app/actions", () => ({
  deleteProject: vi.fn(),
}));
vi.mock("sonner", () => ({
  toast: Object.assign(vi.fn(), { error: vi.fn(), success: vi.fn() }),
}));

import { toast } from "sonner";
import { deleteProject } from "@/app/actions";
import { DeleteProjectDialog } from "./delete-project-dialog";
import type { Project } from "@/lib/types";

const project: Project = {
  id: "p1",
  name: "Alpha",
  createdAt: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(deleteProject).mockReset().mockResolvedValue(undefined);
  vi.mocked(toast.error).mockClear();
  vi.mocked(toast.success).mockClear();
});

it("keeps the delete button disabled until the confirm word is typed", async () => {
  const user = userEvent.setup();
  render(
    <DeleteProjectDialog project={project} open onOpenChange={() => {}} />,
  );

  const dialog = within(await screen.findByRole("dialog"));
  const deleteButton = dialog.getByRole("button", { name: "Delete project" });
  expect(deleteButton).toBeDisabled();

  await user.type(dialog.getByLabelText(/type/i), "nope");
  expect(deleteButton).toBeDisabled();

  await user.clear(dialog.getByLabelText(/type/i));
  await user.type(dialog.getByLabelText(/type/i), "delete");
  expect(deleteButton).toBeEnabled();

  expect(deleteProject).not.toHaveBeenCalled();
});

it("deletes the project once confirmed and closes the dialog", async () => {
  const user = userEvent.setup();
  const onOpenChange = vi.fn();
  render(
    <DeleteProjectDialog
      project={project}
      open
      onOpenChange={onOpenChange}
    />,
  );

  const dialog = within(await screen.findByRole("dialog"));
  await user.type(dialog.getByLabelText(/type/i), "delete");
  await user.click(dialog.getByRole("button", { name: "Delete project" }));

  expect(deleteProject).toHaveBeenCalledWith("p1");
  expect(onOpenChange).toHaveBeenCalledWith(false);
});

it("shows an error toast and stays open when the delete fails", async () => {
  const user = userEvent.setup();
  vi.mocked(deleteProject).mockRejectedValueOnce(new Error("network"));
  const onOpenChange = vi.fn();
  render(
    <DeleteProjectDialog
      project={project}
      open
      onOpenChange={onOpenChange}
    />,
  );

  const dialog = within(await screen.findByRole("dialog"));
  await user.type(dialog.getByLabelText(/type/i), "delete");
  await user.click(dialog.getByRole("button", { name: "Delete project" }));

  expect(toast.error).toHaveBeenCalled();
  expect(onOpenChange).not.toHaveBeenCalledWith(false);
});
