// Spectrum UI Button, copied and adapted from:
// https://github.com/arihantcodes/spectrum-ui/blob/main/components/ui/button.tsx
// Licensed under Apache-2.0. Only the button and its local styling utilities are used.
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#8B83F6] focus-visible:ring-offset-2 focus-visible:ring-offset-[#111113] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#8B83F6] text-[#111113] hover:bg-[#a29cf8]",
        outline: "border border-[#393941] bg-[#19191D] text-[#F4F4F5] hover:bg-[#222228]",
        ghost: "text-[#c4c3ce] hover:bg-[#222228] hover:text-[#F4F4F5]",
      },
      size: {
        default: "px-4 py-2",
        sm: "min-h-9 rounded-md px-3",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Component = asChild ? Slot : "button";
    return <Component ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />;
  },
);
Button.displayName = "SpectrumButton";
