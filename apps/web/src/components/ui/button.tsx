"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

type Variant = "primary" | "default" | "danger" | "ghost";

type ButtonProps = HTMLMotionProps<"button"> & {
  variant?: Variant;
  children: ReactNode;
};

const variantClass: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover shadow-soft",
  default: "border border-line-strong bg-surface-solid text-ink-2 hover:bg-surface",
  danger:
    "border border-[color-mix(in_srgb,var(--color-danger)_40%,transparent)] text-danger hover:bg-[color-mix(in_srgb,var(--color-danger)_10%,transparent)]",
  ghost: "text-ink-2 hover:bg-surface",
};

export function Button({ variant = "default", className, children, disabled, ...props }: ButtonProps) {
  return (
    <motion.button
      whileTap={disabled ? undefined : { scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      className={cn(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variantClass[variant],
        className,
      )}
      disabled={disabled}
      {...props}
    >
      {children}
    </motion.button>
  );
}
