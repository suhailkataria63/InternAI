import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type SkeletonVariant = "shimmer" | "pulse" | "static";
type SkeletonShape = "rectangle" | "circle";

export function skeletonVariants({ variant = "pulse", shape = "rectangle", className = "" }: { variant?: SkeletonVariant; shape?: SkeletonShape; className?: string } = {}) {
  return cn("control-skeleton", `control-skeleton--${variant}`, shape === "circle" && "control-skeleton--circle", className);
}

export function Skeleton({ variant = "pulse", shape = "rectangle", className, ...props }: HTMLAttributes<HTMLDivElement> & { variant?: SkeletonVariant; shape?: SkeletonShape }) {
  return <div aria-hidden="true" className={skeletonVariants({ variant, shape, className })} {...props} />;
}
