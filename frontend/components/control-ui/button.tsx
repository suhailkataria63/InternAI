// Minimal Control UI Button adaptation based on its official registry source:
// https://control-ui.dev/r/button.json
// Uses the registry's Base UI Button primitive and Control UI data attributes;
// InternAI supplies its own theme classes rather than importing the full theme system.
import { Button as BaseButton } from "@base-ui/react/button";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

type ButtonProps = ComponentProps<typeof BaseButton> & {
  variant?: "quiet" | "solid" | "surface";
  size?: "sm" | "md" | "lg";
};

export function Button({ variant = "quiet", size = "sm", className, ...props }: ButtonProps) {
  return (
    <BaseButton
      data-control-ui="button"
      data-control-family="button"
      data-slot="root"
      data-control="true"
      data-variant={variant}
      data-size={size}
      className={cn("control-ui-button", className)}
      {...props}
    />
  );
}
