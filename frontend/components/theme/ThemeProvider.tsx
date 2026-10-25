"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type ColorTheme = "light" | "dark";

type ThemeContextValue = {
  theme: ColorTheme;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "internai-theme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<ColorTheme>("light");

  useEffect(() => {
    const root = document.documentElement;
    const saved = window.localStorage.getItem(STORAGE_KEY);
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const initial: ColorTheme = saved === "dark" || saved === "light"
      ? saved
      : root.dataset.theme === "dark" || (!saved && media.matches) ? "dark" : "light";
    root.dataset.theme = initial;
    setTheme(initial);

    const onPreferenceChange = (event: MediaQueryListEvent) => {
      if (window.localStorage.getItem(STORAGE_KEY)) return;
      const next: ColorTheme = event.matches ? "dark" : "light";
      root.dataset.theme = next;
      setTheme(next);
    };
    media.addEventListener("change", onPreferenceChange);
    return () => media.removeEventListener("change", onPreferenceChange);
  }, []);

  const toggleTheme = useCallback(() => {
    const root = document.documentElement;
    const next: ColorTheme = root.dataset.theme === "dark" ? "light" : "dark";
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduced) {
      root.classList.add("theme-transitioning");
      window.setTimeout(() => root.classList.remove("theme-transitioning"), 460);
    }
    root.dataset.theme = next;
    window.localStorage.setItem(STORAGE_KEY, next);
    setTheme(next);
  }, []);

  const value = useMemo(() => ({ theme, toggleTheme }), [theme, toggleTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useColorTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useColorTheme must be used inside ThemeProvider.");
  return context;
}
