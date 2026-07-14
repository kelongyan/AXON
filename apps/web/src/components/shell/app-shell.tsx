"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Menu, Moon, PanelLeftClose, PanelLeftOpen, Sun, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { useTheme } from "@/components/providers/theme-provider";
import { navigationItems } from "@/lib/navigation";
import { cn } from "@/lib/cn";

const SIDEBAR_KEY = "axon-sidebar-collapsed";
const SIDEBAR_W = 240;
const SIDEBAR_CW = 64;

export function AppShell({ children }: { children: ReactNode }) {
  const { theme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const stored = window.localStorage.getItem(SIDEBAR_KEY);
    if (stored === "true") setCollapsed(true);
  }, []);

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_KEY, String(next));
      return next;
    });
  }, []);

  useEffect(() => setMobileOpen(false), [pathname]);

  const currentLabel = navigationItems.find((item) => item.href === pathname)?.label ?? "";

  return (
    <div className="min-h-screen bg-app text-ink">
      {/* ── Desktop sidebar ── */}
      <motion.aside
        className="fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-line bg-surface/80 backdrop-blur-2xl lg:flex"
        animate={{ width: collapsed ? SIDEBAR_CW : SIDEBAR_W }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
      >
        <div className="flex h-[52px] shrink-0 items-center border-b border-line px-4">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-accent text-sm font-semibold text-white">
              A
            </div>
            <AnimatePresence>
              {!collapsed ? (
                <motion.div
                  className="whitespace-nowrap"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: "auto" }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="text-sm font-semibold text-ink">AXON</div>
                  <div className="text-[11px] text-ink-3">控制台</div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-hidden px-2 py-3">
          {navigationItems.map((item) => {
            const active = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface-solid hover:text-ink",
                )}
                title={collapsed ? item.label : undefined}
              >
                {active ? (
                  <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent" />
                ) : null}
                <Icon size={18} strokeWidth={1.8} className="shrink-0" />
                <AnimatePresence>
                  {!collapsed ? (
                    <motion.span
                      className="whitespace-nowrap"
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.15 }}
                    >
                      {item.label}
                    </motion.span>
                  ) : null}
                </AnimatePresence>
              </Link>
            );
          })}
        </nav>

        <div className="shrink-0 border-t border-line px-2 py-2">
          <button
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-ink-3 transition-colors hover:bg-surface-solid hover:text-ink"
            onClick={toggleCollapse}
            type="button"
            aria-label={collapsed ? "展开侧边栏" : "折叠侧边栏"}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            <AnimatePresence>
              {!collapsed ? (
                <motion.span
                  className="whitespace-nowrap"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.1 }}
                >
                  折叠
                </motion.span>
              ) : null}
            </AnimatePresence>
          </button>
        </div>
      </motion.aside>

      {/* ── Mobile sidebar ── */}
      <AnimatePresence>
        {mobileOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div
              className="absolute inset-0 bg-black/20 backdrop-blur-sm"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              className="absolute inset-y-0 left-0 z-10 flex w-64 flex-col border-r border-line bg-surface-solid shadow-float"
              initial={{ x: "-100%" }}
              animate={{ x: 0 }}
              exit={{ x: "-100%" }}
              transition={{ type: "spring", stiffness: 260, damping: 30 }}
            >
              <div className="flex h-[52px] items-center justify-between border-b border-line px-4">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-semibold text-white">
                    A
                  </div>
                  <span className="text-sm font-semibold text-ink">AXON</span>
                </div>
                <button
                  className="rounded-full p-1.5 text-ink-3 hover:text-ink"
                  onClick={() => setMobileOpen(false)}
                  type="button"
                  aria-label="关闭菜单"
                >
                  <X size={18} />
                </button>
              </div>
              <nav className="flex-1 space-y-0.5 px-2 py-3">
                {navigationItems.map((item) => {
                  const active = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                        active ? "bg-accent-soft text-accent" : "text-ink-2 hover:bg-surface hover:text-ink",
                      )}
                    >
                      <Icon size={18} strokeWidth={1.8} />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
            </motion.aside>
          </div>
        ) : null}
      </AnimatePresence>

      {/* ── Main content ── */}
      <motion.div
        animate={{ paddingLeft: collapsed ? SIDEBAR_CW : SIDEBAR_W }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className="lg:pl-[var(--sidebar-w)]"
        style={{ "--sidebar-w": `${collapsed ? SIDEBAR_CW : SIDEBAR_W}px` } as React.CSSProperties}
      >
        <header className="sticky top-0 z-20 border-b border-line bg-surface/60 backdrop-blur-2xl">
          <div className="flex h-[52px] items-center justify-between px-4 sm:px-6">
            <div className="flex items-center gap-3">
              <button
                className="rounded-lg p-1.5 text-ink-2 transition-colors hover:bg-surface-solid hover:text-ink lg:hidden"
                onClick={() => setMobileOpen(true)}
                type="button"
                aria-label="打开菜单"
              >
                <Menu size={20} />
              </button>
              <nav className="flex items-center gap-1.5 text-sm">
                <span className="text-ink-3">AXON</span>
                {currentLabel ? (
                  <>
                    <span className="text-ink-3">/</span>
                    <span className="font-medium text-ink">{currentLabel}</span>
                  </>
                ) : null}
              </nav>
            </div>
            <button
              onClick={toggleTheme}
              className="rounded-full p-2 text-ink-3 transition-colors hover:bg-surface-solid hover:text-ink"
              type="button"
              aria-label="切换主题"
            >
              {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1200px] px-4 py-6 sm:px-6">{children}</main>
      </motion.div>
    </div>
  );
}
