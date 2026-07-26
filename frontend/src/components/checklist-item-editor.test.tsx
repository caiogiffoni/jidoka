import { useState } from "react";
import { expect, it } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChecklistItemEditor } from "./checklist-item-editor";

function Wrapper({ initial = [] as string[] }) {
  const [items, setItems] = useState(initial);
  return <ChecklistItemEditor items={items} onChange={setItems} />;
}

it("renders one input per item, prefilled with its text", () => {
  render(<Wrapper initial={["First", "Second"]} />);
  expect(screen.getByDisplayValue("First")).toBeInTheDocument();
  expect(screen.getByDisplayValue("Second")).toBeInTheDocument();
});

it("adds a blank row and focuses it when 'Add item' is clicked", async () => {
  const user = userEvent.setup();
  render(<Wrapper initial={["First"]} />);

  await user.click(screen.getByRole("button", { name: /add item/i }));

  const inputs = screen.getAllByPlaceholderText(
    "e.g. write a check-in message in Slack",
  );
  expect(inputs).toHaveLength(2);
  await waitFor(() => expect(inputs[1]).toHaveFocus());
});

it("updates the item's text as the user types", async () => {
  const user = userEvent.setup();
  render(<Wrapper initial={["First"]} />);

  const input = screen.getByDisplayValue("First");
  await user.clear(input);
  await user.type(input, "Renamed");

  expect(screen.getByDisplayValue("Renamed")).toBeInTheDocument();
});

it("removes a row when its remove button is clicked", async () => {
  const user = userEvent.setup();
  render(<Wrapper initial={["First", "Second"]} />);

  const rows = screen.getAllByRole("button", { name: "Remove item" });
  await user.click(rows[0]);

  expect(screen.queryByDisplayValue("First")).not.toBeInTheDocument();
  expect(screen.getByDisplayValue("Second")).toBeInTheDocument();
});

it("uses a custom placeholder when provided", () => {
  function CustomWrapper() {
    const [items, setItems] = useState<string[]>(["x"]);
    return (
      <ChecklistItemEditor
        items={items}
        onChange={setItems}
        itemPlaceholder="Custom placeholder"
      />
    );
  }
  render(<CustomWrapper />);
  expect(screen.getByPlaceholderText("Custom placeholder")).toBeInTheDocument();
});
