"use client";

// Adapted from Spectrum UI Status Badge:
// https://ui.spectrumhq.in/docs/status-badge
import { CircleCheck } from "lucide-react";
import type { ReactNode } from "react";

type StatusBadgeProps = {
  status?: "success";
  children: ReactNode;
};

export function StatusBadge({ status = "success", children }: StatusBadgeProps) {
  return (
    <span className={`spectrum-status-badge spectrum-status-badge--${status}`} role="status">
      <CircleCheck size={15} strokeWidth={2.4} aria-hidden="true" />
      <span>{children}</span>
    </span>
  );
}
