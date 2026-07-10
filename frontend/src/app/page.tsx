import { Board } from "@/components/board/board";
import { ThemeToggle } from "@/components/theme-toggle";

export default function Home() {
  return (
    <main className="flex h-dvh flex-col bg-gradient-to-br from-background via-background to-primary/10">
      <header className="flex items-center gap-3 border-b bg-background/80 px-4 py-3 backdrop-blur sm:px-6">
        <div className="flex size-7 items-center justify-center rounded-md bg-gradient-to-br from-violet-500 to-indigo-600 text-sm font-bold text-white shadow-sm">
          自
        </div>
        <h1 className="text-lg font-bold tracking-tight">Jidoka</h1>
        <p className="hidden text-xs text-muted-foreground sm:block">
          automation with a human touch
        </p>
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>
      <Board />
    </main>
  );
}
