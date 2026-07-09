import Link from "next/link";
import type { ReactNode } from "react";

import { navigationItems } from "@/lib/navigation";

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="min-h-screen bg-zinc-100 text-zinc-950">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-zinc-200 bg-white lg:block">
        <div className="flex h-16 items-center border-b border-zinc-200 px-6">
          <div>
            <div className="text-sm font-semibold uppercase tracking-normal text-teal-700">AgentFlow</div>
            <div className="text-xs text-zinc-500">Control Console</div>
          </div>
        </div>
        <nav className="space-y-1 px-3 py-4">
          {navigationItems.map((item) => (
            <Link
              className="block rounded-md px-3 py-2 text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 hover:text-zinc-950"
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white/95 backdrop-blur">
          <div className="flex min-h-16 flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <div className="text-sm font-semibold text-zinc-950 lg:hidden">AgentFlow</div>
              <div className="text-xs text-zinc-500">AgentFlow Control Console</div>
            </div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1 font-medium text-emerald-700">
                API-first LLM
              </span>
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                Local services
              </span>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </div>
  );
}
