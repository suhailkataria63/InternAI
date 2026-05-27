"use client";

import { useEffect, useState } from "react";

type WelcomeIntroProps = {
  onComplete?: () => void;
};

export default function WelcomeIntro({ onComplete }: WelcomeIntroProps) {
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    const leaveTimer = window.setTimeout(() => setIsLeaving(true), 2600);
    const completeTimer = window.setTimeout(() => onComplete?.(), 3350);

    return () => {
      window.clearTimeout(leaveTimer);
      window.clearTimeout(completeTimer);
    };
  }, [onComplete]);

  return (
    <div
      className={`intro-screen ${isLeaving ? "intro-screen--leaving" : ""}`}
      aria-label="Welcome to InternAI"
    >
      <div className="intro-grid" />
      <div className="intro-orb intro-orb-one" />
      <div className="intro-orb intro-orb-two" />

      <div className="intro-card">
        <div className="intro-logo-wrap">
          <div className="intro-logo">AI</div>
          <div className="intro-logo-ring" />
        </div>

        <p className="intro-kicker">InternAI is booting</p>
        <h1 className="intro-title">Your internship copilot is ready.</h1>
        <p className="intro-copy">
          Resume analysis, skill gaps, cover letters, and application tracking in one intelligent workspace.
        </p>

        <div className="intro-loader" aria-hidden="true">
          <span />
        </div>
      </div>
    </div>
  );
}
