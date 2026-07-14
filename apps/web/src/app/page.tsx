"use client";

import { motion, type Variants } from "framer-motion";
import {
  BarChart3,
  BookOpen,
  Bot,
  PlayCircle,
  Workflow,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/glass-card";
import { MetricCard } from "@/components/ui/glass-card";
import { GlassCard } from "@/components/ui/glass-card";

const metrics = [
  { label: "API 服务", value: "就绪" },
  { label: "数据库", value: "编排中" },
  { label: "Redis", value: "编排中" },
  { label: "MinIO", value: "编排中" },
];

const modules: { name: string; description: string; href: string; icon: LucideIcon }[] = [
  { name: "智能体", description: "版本化的角色与模型配置", href: "/agents", icon: Bot },
  { name: "工作流", description: "可复用的 DAG 定义", href: "/workflows", icon: Workflow },
  { name: "运行记录", description: "执行状态与链路追踪", href: "/runs", icon: PlayCircle },
  { name: "工具", description: "注册表与风险控制", href: "/tools", icon: Wrench },
  { name: "知识库", description: "文档向量化与语义检索", href: "/knowledge-bases", icon: BookOpen },
  { name: "评估", description: "评测任务与质量反馈", href: "/evaluations", icon: BarChart3 },
];

const container: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04 } },
};

const item: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 260, damping: 26 } },
};

export default function DashboardPage() {
  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-6">
      {/* Hero */}
      <motion.section variants={item}>
        <GlassCard className="relative overflow-hidden p-8">
          <div className="pointer-events-none absolute -right-20 -top-20 h-56 w-56 rounded-full bg-accent/8 blur-3xl" />
          <p className="text-label text-accent">仪表盘</p>
          <h1 className="mt-2 text-page-title text-ink">AXON 控制台</h1>
          <p className="mt-2 max-w-xl text-sm text-ink-2">
            面向企业级 AI 应用的多智能体协作平台，覆盖 Agent 编排、工具调用、知识库增强、流程治理与质量评估。
          </p>
        </GlassCard>
      </motion.section>

      {/* Metrics */}
      <section className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        {metrics.map((metric) => (
          <motion.div key={metric.label} variants={item}>
            <MetricCard>
              <div className="text-caption text-ink-3">{metric.label}</div>
              <div className="mt-3 text-metric text-ink">{metric.value}</div>
            </MetricCard>
          </motion.div>
        ))}
      </section>

      {/* Module cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {modules.map(({ name, description, href, icon: Icon }) => (
          <motion.div key={name} variants={item}>
            <Link href={href}>
              <Card className="group h-full cursor-pointer p-5 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-card">
                <div className="flex items-start gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent transition-colors group-hover:bg-accent group-hover:text-white">
                    <Icon size={20} strokeWidth={1.8} />
                  </div>
                  <div>
                    <div className="text-card-title text-ink">{name}</div>
                    <div className="mt-1 text-caption text-ink-2">{description}</div>
                  </div>
                </div>
              </Card>
            </Link>
          </motion.div>
        ))}
      </section>
    </motion.div>
  );
}
