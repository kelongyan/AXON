"use client";

import { MotionConfig } from "framer-motion";
import type { ReactNode } from "react";

import { ToastProvider } from "@/components/ui/toast";
import { ThemeProvider } from "./theme-provider";

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <MotionConfig reducedMotion="user">
        <ToastProvider>{children}</ToastProvider>
      </MotionConfig>
    </ThemeProvider>
  );
}
