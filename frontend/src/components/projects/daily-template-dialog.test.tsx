import { useState } from "react";
import { expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DailyTemplateDialog } from "./daily-template-dialog";
import type { DailyTemplate } from "@/lib/types";

function Wrapper({
  initialTemplate,
  onSave,
}: {
  initialTemplate: DailyTemplate | null;
  onSave: (template: DailyTemplate) => void;
}) {
  const [open, setOpen] = useState(true);
  return (
    <DailyTemplateDialog
      open={open}
      onOpenChange={setOpen}
      projectName="Alpha"
      initialTemplate={initialTemplate}
      onSave={onSave}
    />
  );
}

it("shows Project/Column as fixed and disabled", async () => {
  render(
    <Wrapper initialTemplate={null} onSave={vi.fn()} />,
  );
  const dialog = within(await screen.findByRole("dialog"));

  const projectSelect = dialog.getByRole("combobox");
  expect(projectSelect).toBeDisabled();
  expect(projectSelect).toHaveValue("Alpha");
  expect(dialog.getByRole("button", { name: "To Do" })).toBeDisabled();
});

it("prefills title, description, and checklist from initialTemplate", async () => {
  render(
    <Wrapper
      initialTemplate={{
        title: "Standup",
        description: "Notes",
        checklist: ["Post update"],
      }}
      onSave={vi.fn()}
    />,
  );
  const dialog = within(await screen.findByRole("dialog"));

  expect(dialog.getByLabelText(/title/i)).toHaveValue("Standup");
  expect(dialog.getByLabelText(/description/i)).toHaveValue("Notes");
  expect(dialog.getByDisplayValue("Post update")).toBeInTheDocument();
});

it("trims fields, omits blanks, and saves via onSave then closes", async () => {
  const user = userEvent.setup();
  const onSave = vi.fn();
  render(<Wrapper initialTemplate={null} onSave={onSave} />);
  const dialog = within(await screen.findByRole("dialog"));

  await user.type(dialog.getByLabelText(/title/i), "  Standup  ");
  await user.click(dialog.getByRole("button", { name: /add item/i }));
  await user.type(
    dialog.getByPlaceholderText("e.g. write a check-in message in Slack"),
    "  Post update  ",
  );
  await user.click(dialog.getByRole("button", { name: "Save template" }));

  expect(onSave).toHaveBeenCalledWith({
    title: "Standup",
    description: undefined,
    checklist: ["Post update"],
  });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

it("saves an empty template (no title/description required)", async () => {
  const user = userEvent.setup();
  const onSave = vi.fn();
  render(<Wrapper initialTemplate={null} onSave={onSave} />);
  const dialog = within(await screen.findByRole("dialog"));

  await user.click(dialog.getByRole("button", { name: "Save template" }));

  expect(onSave).toHaveBeenCalledWith({
    title: undefined,
    description: undefined,
    checklist: [],
  });
});

it("closes without saving when Cancel is clicked", async () => {
  const user = userEvent.setup();
  const onSave = vi.fn();
  render(<Wrapper initialTemplate={null} onSave={onSave} />);
  const dialog = within(await screen.findByRole("dialog"));

  await user.type(dialog.getByLabelText(/title/i), "Abandoned");
  await user.click(dialog.getByRole("button", { name: "Cancel" }));

  expect(onSave).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
