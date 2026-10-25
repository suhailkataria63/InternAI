"use client";

import { useColorTheme } from "./ThemeProvider";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useColorTheme();
  const nextTheme = theme === "dark" ? "light" : "dark";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggleTheme}
      aria-label={`Switch to ${nextTheme} theme`}
      aria-pressed={theme === "dark"}
      title={`Switch to ${nextTheme} theme`}
    >
      <span className="theme-toggle__track" aria-hidden="true">
        <span className="theme-toggle__thumb">
          <span className="theme-toggle__icon theme-toggle__icon--sun">
            <svg viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3.5" />
              <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
            </svg>
          </span>
          <span className="theme-toggle__icon theme-toggle__icon--moon">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M20.2 15.3A8.5 8.5 0 0 1 8.7 3.8 8.8 8.8 0 1 0 20.2 15.3Z" />
              <path d="m16.4 4.4.4 1.2 1.2.4-1.2.4-.4 1.2-.4-1.2-1.2-.4 1.2-.4.4-1.2Z" />
            </svg>
          </span>
        </span>
      </span>
    </button>
  );
}
