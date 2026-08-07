"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import { Button } from "@/components/ui/button";
import type { Project } from "@/lib/types";

export interface BoardFiltersState {
  search: string;
  projectId: string;
}

export const emptyFilters: BoardFiltersState = {
  search: "",
  projectId: "",
};

export function BoardFilters({
  projects,
  filters,
  onChange,
}: {
  projects: Project[];
  filters: BoardFiltersState;
  onChange: (filters: BoardFiltersState) => void;
}) {
  const hasFilters = filters.search.trim() !== "" || filters.projectId !== "";

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 pt-3 sm:px-6">
      <div className="relative flex-1 basis-48">
        <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          placeholder="Search tasks..."
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          className="h-8 pl-8"
          aria-label="Search tasks"
        />
      </div>
      <NativeSelect
        aria-label="Filter by project"
        value={filters.projectId}
        onChange={(e) => onChange({ ...filters, projectId: e.target.value })}
        className="w-40"
      >
        <option value="">All projects</option>
        {projects.map((project) => (
          <option key={project.id} value={project.id}>
            {project.name}
          </option>
        ))}
      </NativeSelect>
      {hasFilters && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange(emptyFilters)}
          className="h-8 gap-1 px-2 text-muted-foreground"
        >
          <X className="size-4" />
          Clear
        </Button>
      )}
    </div>
  );
}
