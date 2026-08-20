import Link from "next/link";
import { LayoutDashboard } from "lucide-react";
import { requireAuth } from "@/app/actions";
import { Board } from "@/components/board/board";
import { AddTaskDialog } from "@/components/board/add-task-dialog";
import { ArchivedTasksDialog } from "@/components/board/archived-tasks-dialog";
import { PomodoroMenu } from "@/components/pomodoro/pomodoro-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/auth/user-menu";
import { AgentChatButton } from "@/components/agent/agent-chat-button";
import { MobileHeaderMenu } from "@/components/mobile-header-menu";
import { Button } from "@/components/ui/button";
import { fetchProjects, fetchTasksByColumn } from "@/lib/api";

export default async function BoardPage() {
  const user = await requireAuth();
  const [initialTasks, projects] = await Promise.all([
    fetchTasksByColumn(),
    fetchProjects(),
  ]);
  return (
    <main className="flex h-dvh flex-col bg-background">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-background px-4 py-3 sm:px-6">
        <h1 className="flex items-center gap-2 text-sm font-semibold tracking-tight">
          <span aria-hidden className="text-base leading-none">
            自
          </span>
          Jidoka
        </h1>
        <p className="hidden text-xs text-muted-foreground sm:block">
          automation with a human touch
        </p>
        <div className="ml-auto hidden flex-wrap items-center justify-end gap-2 sm:flex">
          <AddTaskDialog projects={projects} />
          <ArchivedTasksDialog />
          <AgentChatButton />
          <Button
            variant="ghost"
            size="icon"
            aria-label="Projects & time dashboard"
            asChild
          >
            <Link href="/">
              <LayoutDashboard />
            </Link>
          </Button>
          <PomodoroMenu />
          <ThemeToggle />
          <UserMenu user={user} />
        </div>
        <MobileHeaderMenu
          items={[
            { id: "add", label: "Add task", node: <AddTaskDialog projects={projects} /> },
            { id: "archive", label: "Archived tasks", node: <ArchivedTasksDialog /> },
            { id: "agent", label: "Agent chat", node: <AgentChatButton /> },
            {
              id: "dashboard",
              label: "Dashboard",
              closeOnClick: true,
              node: (
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Projects & time dashboard"
                  asChild
                >
                  <Link href="/">
                    <LayoutDashboard />
                  </Link>
                </Button>
              ),
            },
            { id: "pomodoro", label: "Pomodoro", node: <PomodoroMenu /> },
            { id: "theme", label: "Theme", node: <ThemeToggle /> },
            { id: "user", label: "Account", node: <UserMenu user={user} /> },
          ]}
        />
      </header>
      <Board initialTasks={initialTasks} projects={projects} />
    </main>
  );
}
