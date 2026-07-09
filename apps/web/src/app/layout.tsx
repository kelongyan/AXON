import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentFlow Console",
  description: "AgentFlow multi-agent workflow console",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}

