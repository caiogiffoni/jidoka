import { COLUMNS, type ColumnId, type TasksByColumn } from "./types";

export type ProjectTaskCounts = Record<ColumnId, number>;

export function countTasksByProject(
  tasks: TasksByColumn,
): Record<string, ProjectTaskCounts> {
  const counts: Record<string, ProjectTaskCounts> = {};
  for (const column of COLUMNS) {
    for (const task of tasks[column.id]) {
      if (!task.projectId) continue;
      const entry = (counts[task.projectId] ??= {
        todo: 0,
        in_progress: 0,
        done: 0,
      });
      entry[column.id] += 1;
    }
  }
  return counts;
}
