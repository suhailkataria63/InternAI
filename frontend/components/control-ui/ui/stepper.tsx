"use client";

import { createContext, useContext, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type StepperContextValue = { value: number; onValueChange?: (value: number) => void; orientation: "horizontal" | "vertical" };
type ItemContextValue = { step: number; current: boolean; complete: boolean };
const StepperContext = createContext<StepperContextValue>({ value: 0, orientation: "vertical" });
const ItemContext = createContext<ItemContextValue>({ step: 0, current: false, complete: false });

export function Stepper({ value, onValueChange, orientation = "vertical", className, children }: { value: number; onValueChange?: (value: number) => void; orientation?: "horizontal" | "vertical"; contentMode?: "all" | "current"; className?: string; children: ReactNode }) {
  return <StepperContext.Provider value={{ value, onValueChange, orientation }}><div className={cn("control-stepper", className)} data-orientation={orientation}>{children}</div></StepperContext.Provider>;
}

export function StepperList({ className, ...props }: HTMLAttributes<HTMLOListElement>) {
  return <ol {...props} className={cn("control-stepper-list", className)} />;
}

export function StepperItem({ step, className, children, ...props }: HTMLAttributes<HTMLLIElement> & { step: number }) {
  const state = useContext(StepperContext);
  const item = { step, current: state.value === step, complete: state.value > step };
  return <ItemContext.Provider value={item}><li {...props} className={cn("control-stepper-item", className)} data-state={item.current ? "current" : item.complete ? "complete" : "upcoming"}>{children}</li></ItemContext.Provider>;
}

export function StepperTrigger({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  const item = useContext(ItemContext);
  return <div {...props} className={cn("control-stepper-trigger", className)} aria-current={item.current ? "step" : undefined}>{children}</div>;
}

export function StepperIndicator({ className, children, ...props }: HTMLAttributes<HTMLSpanElement>) {
  const item = useContext(ItemContext);
  return <span {...props} className={cn("control-stepper-indicator", className)} aria-hidden="true">{children ?? (item.complete ? "✓" : item.step + 1)}</span>;
}

export function StepperTitle({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...props} className={cn("control-stepper-title", className)} />;
}

export function StepperDescription({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...props} className={cn("control-stepper-description", className)} />;
}

export function StepperSeparator({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...props} className={cn("control-stepper-separator", className)} aria-hidden="true" />;
}

export function StepperContent({ value, className, children, ...props }: HTMLAttributes<HTMLDivElement> & { value: number }) {
  const current = useContext(StepperContext).value === value;
  if (!current) return null;
  return <div {...props} className={cn("control-stepper-content", className)}>{children}</div>;
}
