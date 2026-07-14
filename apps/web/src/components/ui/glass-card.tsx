import { type ElementType, type FormHTMLAttributes, type HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

type BaseProps = HTMLAttributes<HTMLDivElement> & {
  as?: "div" | "section" | "article";
};

type FormProps = FormHTMLAttributes<HTMLFormElement> & {
  as: "form";
};

type CardProps = BaseProps | FormProps;

const glassClass = "rounded-2xl border border-line bg-surface shadow-card backdrop-blur-xl";
const solidClass = "rounded-2xl border border-line bg-surface-solid shadow-soft";
const metricClass = "rounded-2xl bg-surface-solid p-5";

function resolveTag(as?: string): ElementType {
  return (as ?? "div") as ElementType;
}

export function GlassCard(props: CardProps) {
  const { className, as, ...rest } = props as HTMLAttributes<HTMLElement> & { as?: string };
  const Tag = resolveTag(as);
  return <Tag className={cn(glassClass, className)} {...rest} />;
}

export function Card(props: CardProps) {
  const { className, as, ...rest } = props as HTMLAttributes<HTMLElement> & { as?: string };
  const Tag = resolveTag(as);
  return <Tag className={cn(solidClass, className)} {...rest} />;
}

export function MetricCard(props: CardProps) {
  const { className, as, ...rest } = props as HTMLAttributes<HTMLElement> & { as?: string };
  const Tag = resolveTag(as);
  return <Tag className={cn(metricClass, className)} {...rest} />;
}
