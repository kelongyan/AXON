import { cn } from "@/lib/cn";

export function Skeleton({ className, shimmer = false }: { className?: string; shimmer?: boolean }) {
  return (
    <div
      className={cn("rounded-xl", shimmer ? "skeleton-shimmer" : "animate-pulse bg-line", className)}
      aria-hidden
    />
  );
}
