"use client";

import MockAuthActions from "@/components/MockAuthActions";
import GooeyNav, { type GooeyNavItem } from "@/components/react-bits/GooeyNav";
import ThemeToggle from "@/components/theme/ThemeToggle";
import { useColorTheme } from "@/components/theme/ThemeProvider";

export type NavigationKey = "home" | "analyze" | "studio" | "tracker";

type WorkspaceNavigationProps = {
  activeKey: NavigationKey;
  onNavigate: (key: NavigationKey) => void;
};

const destinations: Array<{ key: NavigationKey; label: string }> = [
  { key: "home", label: "Home" },
  { key: "analyze", label: "Analyze" },
  { key: "studio", label: "AI Studio" },
  { key: "tracker", label: "Tracker" },
];

export default function WorkspaceNavigation({
  activeKey,
  onNavigate,
}: WorkspaceNavigationProps) {
  const { theme } = useColorTheme();
  const items: GooeyNavItem[] = destinations.map(({ key, label }) => ({
    label,
    href: `#${key}`,
    disabled: false,
  }));
  const activeIndex = Math.max(0, destinations.findIndex(({ key }) => key === activeKey));

  return (
    <header className="global-navbar">
      <button
        type="button"
        className="global-brand"
        onClick={() => onNavigate("home")}
        aria-label="Go to InternAI home"
      >
        <span className="landing-mark" aria-hidden="true">i</span>
        <span>InternAI</span>
      </button>

      <GooeyNav
        ariaLabel="Primary navigation"
        className="primary-gooey-nav"
        items={items}
        activeIndex={activeIndex}
        onChange={(index) => {
          const destination = destinations[index];
          if (destination && !items[index]?.disabled) onNavigate(destination.key);
        }}
        theme={theme}
        color={theme === "dark" ? "#9787FF" : "#6858D8"}
        activeTextColor={theme === "dark" ? "#211d38" : "#FFFFFF"}
        size="sm"
        frame
        particleCount={7}
        spread={28}
        animationTime={520}
        timeVariance={100}
        gooeyness={0.5}
        wobble={0.2}
        hoverEffect
      />

      <div className="mobile-navigation">
        <label className="visually-hidden" htmlFor="mobile-primary-navigation">Navigate to</label>
        <select
          id="mobile-primary-navigation"
          value={activeKey}
          onChange={(event) => onNavigate(event.target.value as NavigationKey)}
          aria-label="Navigate to"
        >
          {destinations.map(({ key, label }) => (
            <option
              key={key}
              value={key}
            >
              {label}
            </option>
          ))}
        </select>
      </div>

      <div className="global-nav-actions">
        <ThemeToggle />
        <MockAuthActions />
      </div>
    </header>
  );
}
