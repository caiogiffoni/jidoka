"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

type Theme = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "system",
  resolvedTheme: "light",
  setTheme: () => {},
});

const STORAGE_KEY = "theme";
const THEMES: ResolvedTheme[] = ["light", "dark"];

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme !== "system") return theme;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  const resolved = resolveTheme(theme);
  const html = document.documentElement;
  html.classList.remove(...THEMES);
  html.classList.add(resolved);
  html.style.colorScheme = resolved;
}

function readStoredTheme(defaultTheme: Theme): Theme {
  if (typeof window === "undefined") return defaultTheme;
  try {
    return (window.localStorage.getItem(STORAGE_KEY) as Theme | null) ?? defaultTheme;
  } catch {
    return defaultTheme;
  }
}

export function ThemeProvider({
  children,
  defaultTheme = "system",
}: {
  children: React.ReactNode;
  defaultTheme?: Theme;
}) {
  const [theme, setThemeState] = useState<Theme>(() =>
    readStoredTheme(defaultTheme),
  );

  useEffect(() => {
    if (theme !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyTheme("system");
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, [theme]);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY) return;
      const next = (event.newValue as Theme | null) ?? defaultTheme;
      setThemeState(next);
    }
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [defaultTheme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Ignore storage errors.
    }
    applyTheme(next);
  }, []);

  const value = useMemo(
    () => ({
      theme,
      resolvedTheme: resolveTheme(theme),
      setTheme,
    }),
    [theme, setTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
