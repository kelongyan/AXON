"use client";

import { Moon, Sun } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { useTheme } from "@/components/providers/theme-provider";
import { navigationItems } from "@/lib/navigation";

export function AppShell({ children }: { children: ReactNode }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="min-h-screen bg-app text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-surface/80 backdrop-blur-2xl lg:block">
        <div className="flex h-16 items-center border-b border-line px-6">
          <div>
            <div className="text-sm font-semibold uppercase tracking-wide text-accent">AgentFlow</div>
            <div className="text-xs text-ink-3">控制台</div>
          </div>
        </div>
        <nav className="space-y-1 px-3 py-4">
          {navigationItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink-2 transition-colors hover:bg-surface hover:text-ink"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-line-strong transition-colors group-hover:bg-accent" />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-line bg-surface/70 backdrop-blur-2xl">
          <div className="flex min-h-16 flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <div className="text-sm font-semibold text-ink lg:hidden">AgentFlow</div>
              <div className="text-xs text-ink-3">AgentFlow 控制台</div>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full border border-success/30 bg-success/10 px-2.5 py-1 font-medium text-success">
                API 优先大模型
              </span>
              <span className="rounded-full border border-warning/30 bg-warning/10 px-2.5 py-1 font-medium text-warning">
                本地服务
              </span>
              <button
                onClick={toggleTheme}
                className="rounded-full border border-line p-2 text-ink-2 transition-colors hover:bg-surface hover:text-ink"
                type="button"
                aria-label="切换主题"
              >
                {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
