"use client";

import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";

type AnimatedCardProps = {
  icon: ReactNode;
  title: string;
  description: string;
  hints: string[];
  onSelect: () => void;
};

/** Adapted from Spectrum UI's Animated Card source; interaction remains a real button. */
export function AnimatedCard({ icon, title, description, hints, onSelect }: AnimatedCardProps) {
  const reduceMotion = useReducedMotion();
  return (
    <motion.button
      type="button"
      className="studio-choice-card"
      onClick={onSelect}
      whileHover={reduceMotion ? undefined : { y: -3, scale: 1.008 }}
      whileTap={reduceMotion ? undefined : { scale: 0.995 }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.2, ease: "easeOut" }}
    >
      <span className="studio-choice-icon" aria-hidden="true">{icon}</span>
      <span className="studio-choice-copy">
        <span className="studio-choice-title">{title}</span>
        <span className="studio-choice-description">{description}</span>
        <span className="studio-choice-hints">{hints.map((hint) => <span key={hint}>{hint}</span>)}</span>
      </span>
      <span className="studio-choice-arrow" aria-hidden="true">→</span>
    </motion.button>
  );
}
