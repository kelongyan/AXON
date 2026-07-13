import { type ElementType, type FormHTMLAttributes, type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type BaseProps = HTMLAttributes<HTMLDivElement> & {
  as?: "div" | "section" | "article";
};

type FormProps = FormHTMLAttributes<HTMLFormElement> & {
  as: "form";
};

type GlassCardProps = BaseProps | FormProps;

const glassClass = "rounded-2xl border border-line bg-surface shadow-card backdrop-blur-xl";

export function GlassCard(props: GlassCardProps) {
  const { className, as, ...rest } = props as HTMLAttributes<HTMLElement> & { as?: string };
  const Tag = (as ?? "div") as ElementType;
  return <Tag className={cn(glassClass, className)} {...rest} />;
}
