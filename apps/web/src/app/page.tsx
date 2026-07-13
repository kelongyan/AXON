"use client";

import { motion, useScroll, useTransform, type Variants } from "framer-motion";
import { useRef } from "react";

import { GlassCard } from "@/components/ui/glass-card";
import { Skeleton } from "@/components/ui/skeleton";

const metrics = [
  { label: "API 服务", value: "就绪" },
  { label: "数据库", value: "编排中" },
  { label: "Redis", value: "编排中" },
  { label: "MinIO", value: "编排中" },
];

const modules = [
  ["智能体", "版本化的角色与模型配置"],
  ["工作流", "可复用的 DAG 定义"],
  ["运行记录", "执行状态与链路追踪"],
  ["工具", "注册表与风险控制"],
  ["知识库", "文档向量化与语义检索"],
  ["评估", "评测任务与质量反馈"],
];

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 260, damping: 26 } },
};

export default function DashboardPage() {
  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const heroY = useTransform(scrollYProgress, [0, 1], [0, 36]);

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
      <motion.section
        ref={heroRef}
        style={{ y: heroY }}
        variants={item}
        className="relative overflow-hidden rounded-3xl border border-line bg-surface p-8 shadow-card backdrop-blur-xl"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-accent/10 blur-3xl" />
        <p className="text-xs font-semibold uppercase tracking-wide text-accent">仪表盘</p>
        <h1 className="mt-2 text-3xl font-semibold text-ink">阶段 0 基础底座</h1>
        <p className="mt-2 max-w-xl text-sm text-ink-2">
          面向企业级 AI 应用的多智能体协作平台，覆盖 Agent 编排、工具调用、知识库增强、流程治理与质量评估。
        </p>
      </motion.section>

      <section className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {metrics.map((metric) => (
          <motion.div key={metric.label} variants={item}>
            <GlassCard className="p-5">
              <div className="text-sm text-ink-3">{metric.label}</div>
              <div className="mt-3 text-2xl font-semibold text-ink">{metric.value}</div>
            </GlassCard>
          </motion.div>
        ))}
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {modules.map(([name, description]) => (
          <motion.div key={name} variants={item}>
            <GlassCard className="h-full p-6 transition-transform duration-300 hover:-translate-y-0.5">
              <div className="text-base font-semibold text-ink">{name}</div>
              <div className="mt-2 text-sm text-ink-2">{description}</div>
            </GlassCard>
          </motion.div>
        ))}
      </section>

      <Skeleton className="h-24 w-full" />
    </motion.div>
  );
}
