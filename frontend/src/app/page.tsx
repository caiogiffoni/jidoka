import { Board } from "@/components/board/board";
import { AddTaskDialog } from "@/components/board/add-task-dialog";
import { PomodoroMenu } from "@/components/pomodoro/pomodoro-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { fetchTasksByColumn } from "@/lib/api";

export default async function Home() {
  const initialTasks = await fetchTasksByColumn();
  return (
    <main className="flex h-dvh flex-col bg-background">
      <header className="flex items-center gap-3 border-b bg-background px-4 py-3 sm:px-6">
        <h1 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <span aria-hidden className="text-base leading-none">
            自
          </span>
          Jidoka
        </h1>
        <p className="hidden text-xs text-muted-foreground sm:block">
          automation with a human touch
        </p>
        <div className="ml-auto flex items-center gap-2">
          <AddTaskDialog />
          <PomodoroMenu />
          <ThemeToggle />
        </div>
      </header>
      <Board initialTasks={initialTasks} />
    </main>
  );
}
