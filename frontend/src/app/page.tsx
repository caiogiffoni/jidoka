import { Board } from "@/components/board/board";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <header className="border-b px-6 py-3">
        <h1 className="text-lg font-bold tracking-tight">Jidoka</h1>
      </header>
      <Board />
    </main>
  );
}
