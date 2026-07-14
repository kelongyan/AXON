"use client";

import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle, Info, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

import { cn } from "@/lib/cn";

type ToastTone = "info" | "success" | "danger";

type ToastItem = {
  id: number;
  message: string;
  tone: ToastTone;
};

type ToastContextValue = {
  toast: (message: string, tone?: ToastTone) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const toast = useCallback((message: string, tone: ToastTone = "info") => {
    const id = nextId++;
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-[60] flex flex-col gap-2">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              className="pointer-events-auto"
              key={t.id}
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
            >
              <ToastCard message={t.message} tone={t.tone} onDismiss={() => dismiss(t.id)} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast 必须在 ToastProvider 内使用");
  }
  return context;
}

const toneConfig = {
  info: { icon: Info, className: "border-line text-ink-2" },
  success: { icon: CheckCircle, className: "border-success/25 text-success" },
  danger: { icon: XCircle, className: "border-danger/25 text-danger" },
} as const;

function ToastCard({
  message,
  tone,
  onDismiss,
}: {
  message: string;
  tone: ToastTone;
  onDismiss: () => void;
}) {
  const { icon: Icon, className } = toneConfig[tone];
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-xl border bg-surface-solid px-4 py-3 shadow-card",
        className,
      )}
      role="status"
    >
      <Icon size={18} strokeWidth={1.5} />
      <span className="min-w-0 flex-1 text-sm text-ink">{message}</span>
      <button
        className="shrink-0 text-ink-3 transition-colors hover:text-ink"
        onClick={onDismiss}
        type="button"
        aria-label="关闭"
      >
        <span className="text-xs font-medium">✕</span>
      </button>
    </div>
  );
}
