import Link from "next/link";
import { KanbanSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { WeeklyBarChart } from "@/components/projects/weekly-bar-chart";
import { fetchDailyStats, fetchProjects } from "@/lib/api";
import { buildWeeklyChart } from "@/lib/weekly-chart";

export default async function DashboardPage() {
  const [projects, stats] = await Promise.all([
    fetchProjects(),
    fetchDailyStats(7),
  ]);
  const days = buildWeeklyChart(projects, stats, 7);

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
          <CreateProjectDialog />
          <Button variant="ghost" size="icon" aria-label="Board" asChild>
            <Link href="/board">
              <KanbanSquare />
            </Link>
          </Button>
          <ThemeToggle />
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <WeeklyBarChart days={days} projects={projects} />
      </div>
    </main>
  );
}
