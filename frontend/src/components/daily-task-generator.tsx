"use client";

import { useEffect } from "react";
import { toast } from "sonner";
import { generateDailyTasks } from "@/app/actions";

// "Every time we log in" has no real event yet - there's no auth/login
// system built (see CLAUDE.md). Local-day-since-last-run is the closest
// available proxy: this fires once per browser-local calendar day,
// regardless of which route is entered first. The server side is
// idempotent per UTC day via Project.daily_last_generated, so a stale or
// cleared localStorage value just costs a redundant, harmless call.
const STORAGE_KEY = "jidoka-daily-tasks-last-run";

function todayLocal(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export function DailyTaskGenerator() {
  useEffect(() => {
    const today = todayLocal();
    if (localStorage.getItem(STORAGE_KEY) === today) return;
    localStorage.setItem(STORAGE_KEY, today);

    generateDailyTasks()
      .then(({ created }) => {
        if (created > 0) {
          toast.success(
            created === 1
              ? "1 daily task created"
              : `${created} daily tasks created`,
          );
        }
      })
      .catch((error) => {
        console.error("Could not generate daily tasks:", error);
      });
  }, []);

  return null;
}
