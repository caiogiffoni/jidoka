import { expect, it, vi } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BoardFilters, emptyFilters, type BoardFiltersState } from "./board-filters";
import type { Project } from "@/lib/types";

const projects: Project[] = [
  {
    id: "p1",
    name: "Alpha",
    createdAt: "2026-01-01T00:00:00Z",
    dailyEnabled: false,
    dailyTemplate: null,
  },
  {
    id: "p2",
    name: "Beta",
    createdAt: "2026-01-02T00:00:00Z",
    dailyEnabled: false,
    dailyTemplate: null,
  },
];

function ControlledBoardFilters() {
  const [filters, setFilters] = useState<BoardFiltersState>(emptyFilters);
  return (
    <BoardFilters projects={projects} filters={filters} onChange={setFilters} />
  );
}

it("updates search and project filters", async () => {
  const user = userEvent.setup();

  render(<ControlledBoardFilters />);

  await user.type(screen.getByLabelText("Search tasks"), "review");
  expect(screen.getByLabelText("Search tasks")).toHaveValue("review");

  await user.selectOptions(screen.getByLabelText("Filter by project"), "p2");
  expect(screen.getByLabelText("Filter by project")).toHaveValue("p2");
});

it("clears active filters when the clear button is clicked", async () => {
  const user = userEvent.setup();
  const onChange = vi.fn();

  render(
    <BoardFilters
      projects={projects}
      filters={{ search: "find me", projectId: "p1" }}
      onChange={onChange}
    />,
  );

  await user.click(screen.getByRole("button", { name: /clear/i }));
  expect(onChange).toHaveBeenCalledWith(emptyFilters);
});

it("hides the clear button when no filters are active", () => {
  render(
    <BoardFilters
      projects={projects}
      filters={emptyFilters}
      onChange={vi.fn()}
    />,
  );

  expect(
    screen.queryByRole("button", { name: /clear/i }),
  ).not.toBeInTheDocument();
});
