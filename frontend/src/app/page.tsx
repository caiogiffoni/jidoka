import Link from "next/link";
import { KanbanSquare } from "lucide-react";
import { requireAuth } from "@/app/actions";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserMenu } from "@/components/auth/user-menu";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { ProjectList } from "@/components/projects/project-list";
import { WeeklyBarChart } from "@/components/projects/weekly-bar-chart";
import { MobileHeaderMenu } from "@/components/mobile-header-menu";
import { fetchDailyStats, fetchProjects, fetchTasksByColumn } from "@/lib/api";
import { buildWeeklyChart } from "@/lib/weekly-chart";
import { countTasksByProject } from "@/lib/project-task-counts";

export default async function DashboardPage() {
  const user = await requireAuth();
  const [projects, stats, tasks] = await Promise.all([
    fetchProjects(),
    fetchDailyStats(7),
    fetchTasksByColumn(),
  ]);
  const days = buildWeeklyChart(projects, stats, 7);
  const taskCounts = countTasksByProject(tasks);

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
          <CreateProjectDialog />
          <Button variant="ghost" size="icon" aria-label="Board" asChild>
            <Link href="/board">
              <KanbanSquare />
            </Link>
          </Button>
          <ThemeToggle />
          <UserMenu user={user} />
        </div>
        <MobileHeaderMenu
          items={[
            { id: "project", label: "Add project", node: <CreateProjectDialog /> },
            {
              id: "board",
              label: "Board",
              closeOnClick: true,
              node: (
                <Button variant="ghost" size="icon" aria-label="Board" asChild>
                  <Link href="/board">
                    <KanbanSquare />
                  </Link>
                </Button>
              ),
            },
            { id: "theme", label: "Theme", node: <ThemeToggle /> },
            { id: "user", label: "Account", node: <UserMenu user={user} /> },
          ]}
        />
      </header>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="grid grid-cols-1 items-start gap-4 sm:grid-cols-2">
          <WeeklyBarChart days={days} projects={projects} />
          <ProjectList projects={projects} taskCounts={taskCounts} />
        </div>
      </div>
    </main>
  );
}
