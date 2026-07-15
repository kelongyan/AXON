"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import {
  ChevronDown,
  Eye,
  Play,
  Plus,
  Trash2,
  Upload,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { type Agent, fetchAgents } from "@/lib/agents";
import { type KnowledgeBase, fetchKnowledgeBases } from "@/lib/knowledge-bases";
import { type Tool, fetchTools } from "@/lib/tools";
import {
  type BuilderNode,
  type BuilderNodeData,
  applyNodeStatuses,
  buildApprovalBuilderNode,
  buildAgentBuilderNode,
  buildConditionBuilderNode,
  buildDefaultBuilderGraph,
  buildEndBuilderNode,
  buildRetrievalBuilderNode,
  buildToolBuilderNode,
  builderGraphToWorkflowGraph,
  mapRunStepsToNodeStatus,
  selectDefaultToolNodeReferences,
  workflowGraphToBuilderGraph,
} from "@/lib/workflow-builder";
import {
  type Workflow,
  type WorkflowDetail,
  type WorkflowFormValues,
  type WorkflowRun,
  createWorkflow,
  createWorkflowRun,
  executeRun,
  fetchWorkflow,
  fetchWorkflows,
  parseRunInput,
  publishWorkflowVersion,
} from "@/lib/workflows";
import { errorMessage } from "@/lib/error-message";
import { statusLabel, statusTone, type Tone } from "@/lib/status-label";
import { useRunAction } from "@/lib/use-run-action";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Card } from "@/components/ui/glass-card";
import { MessageBanner } from "@/components/ui/message-banner";
import { Sheet } from "@/components/ui/sheet";
import { StatusPill } from "@/components/ui/status-pill";

const defaultWorkflowForm: WorkflowFormValues = {
  name: "可视化 RAG 工作流",
  description: "阶段 6 可视化工作流编排流程。",
};

const defaultRunInput = JSON.stringify(
  {
    topic: "AgentFlow RAG 知识库如何接入工作流？",
    audience: "技术负责人",
    max_words: 900,
  },
  null,
  2,
);

const nodeTypes: NodeTypes = { workflowNode: WorkflowNodeCard };
type FlowNode = Node<BuilderNodeData, "workflowNode">;
type FlowEdge = Edge;

const nodeToneClass: Record<Tone, string> = {
  ready: "bg-success/10 text-success",
  neutral: "bg-surface-solid text-ink-2",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  danger: "bg-danger/10 text-danger",
  info: "bg-info/10 text-info",
};

const nodeBorderColor: Record<string, string> = {
  agent: "border-l-accent",
  retrieval: "border-l-success",
  tool: "border-l-warning",
  condition: "border-l-violet-400",
  approval: "border-l-amber-400",
  end: "border-l-ink-3",
  start: "border-l-info",
};

export function WorkflowsConsole() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [tools, setTools] = useState<Tool[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [formValues, setFormValues] = useState<WorkflowFormValues>(defaultWorkflowForm);
  const [runInputText, setRunInputText] = useState(defaultRunInput);
  const [lastRun, setLastRun] = useState<WorkflowRun | null>(null);
  const { busy, message, run, setMessage } = useRunAction();
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);
  const [workflowDropdownOpen, setWorkflowDropdownOpen] = useState(false);
  const [createPanelOpen, setCreatePanelOpen] = useState(false);
  const [jsonPreviewOpen, setJsonPreviewOpen] = useState(false);

  const selectedAgent = agents.find((agent) => agent.current_version_id) ?? null;
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) as BuilderNode | undefined,
    [nodes, selectedNodeId],
  );
  const graphPreview = useMemo(
    () => JSON.stringify(builderGraphToWorkflowGraph(nodes as BuilderNode[], edges), null, 2),
    [edges, nodes],
  );

  useEffect(() => {
    void loadInitialData();
  }, []);

  useEffect(() => {
    if (selectedWorkflowId) {
      void loadWorkflowDetail(selectedWorkflowId);
    } else {
      setDetail(null);
    }
  }, [selectedWorkflowId]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((current) =>
        addEdge(
          {
            ...connection,
            id: `edge_${connection.source}_${connection.target}_${Date.now()}`,
            type: "default",
          },
          current,
        ),
      );
    },
    [setEdges],
  );

  async function loadInitialData() {
    await run(async () => {
      const [nextAgents, nextWorkflows, nextKnowledgeBases, nextTools] = await Promise.all([
        fetchAgents(),
        fetchWorkflows(),
        fetchKnowledgeBases(),
        fetchTools(),
      ]);
      setAgents(nextAgents);
      setWorkflows(nextWorkflows);
      setKnowledgeBases(nextKnowledgeBases);
      setTools(nextTools);
      setSelectedWorkflowId((current) => current ?? nextWorkflows[0]?.id ?? null);
      if (nextWorkflows.length === 0) {
        loadTemplateGraph(nextAgents[0]?.current_version_id ?? null);
      }
    });
  }

  async function reloadWorkflows(selectWorkflowId?: string) {
    const nextWorkflows = await fetchWorkflows();
    setWorkflows(nextWorkflows);
    if (selectWorkflowId) {
      setSelectedWorkflowId(selectWorkflowId);
      return;
    }
    if (selectedWorkflowId && nextWorkflows.some((workflow) => workflow.id === selectedWorkflowId)) {
      return;
    }
    setSelectedWorkflowId(nextWorkflows[0]?.id ?? null);
  }

  async function loadWorkflowDetail(workflowId: string) {
    try {
      const nextDetail = await fetchWorkflow(workflowId);
      setDetail(nextDetail);
      setFormValues({ name: nextDetail.name, description: nextDetail.description });
      if (nextDetail.current_version?.graph) {
        const builderGraph = workflowGraphToBuilderGraph(nextDetail.current_version.graph);
        setNodes(builderGraph.nodes as FlowNode[]);
        setEdges(builderGraph.edges as FlowEdge[]);
        setSelectedNodeId(builderGraph.nodes[0]?.id ?? null);
      }
    } catch (error) {
      setMessage(errorMessage(error));
    }
  }

  function loadTemplateGraph(agentVersionId: string | null = selectedAgent?.current_version_id ?? null) {
    if (!agentVersionId) {
      setMessage("请先创建并发布一个智能体版本，再加载模板");
      return;
    }
    const graph = buildDefaultBuilderGraph(agentVersionId);
    setNodes(graph.nodes as FlowNode[]);
    setEdges(graph.edges as FlowEdge[]);
    setSelectedNodeId(graph.nodes[0]?.id ?? null);
    setMessage("已加载可视化 开始 → 智能体 → 结束 模板");
  }

  function addNode(kind: "agent" | "retrieval" | "tool" | "condition" | "approval" | "end") {
    const offset = nodes.length * 45;
    if (kind === "agent") {
      const agentVersionId = selectedAgent?.current_version_id;
      if (!agentVersionId) {
        setMessage("请先选择或创建智能体，再添加智能体节点");
        return;
      }
      const node = buildAgentBuilderNode({
        id: `node_agent_${Date.now()}`,
        agentVersionId,
        x: 320 + offset,
        y: 260,
      });
      setNodes((current) => [...current, node as FlowNode]);
      setSelectedNodeId(node.id);
      return;
    }
    if (kind === "retrieval") {
      const node = buildRetrievalBuilderNode({
        id: `node_retrieval_${Date.now()}`,
        knowledgeBaseIds: knowledgeBases[0]?.id ? [knowledgeBases[0].id] : [],
        x: 320 + offset,
        y: 40,
      });
      setNodes((current) => [...current, node as FlowNode]);
      setSelectedNodeId(node.id);
      return;
    }
    if (kind === "tool") {
      const selection = selectDefaultToolNodeReferences(agents, tools);
      if (!selection.agentId || !selection.toolId) {
        setMessage("请先创建智能体并初始化一个启用中的工具，再添加工具节点");
        return;
      }
      const node = buildToolBuilderNode({
        id: `node_tool_${Date.now()}`,
        agentId: selection.agentId,
        toolId: selection.toolId,
        x: 480 + offset,
        y: 260,
      });
      setNodes((current) => [...current, node as FlowNode]);
      setSelectedNodeId(node.id);
      return;
    }
    if (kind === "condition") {
      const node = buildConditionBuilderNode({
        id: `node_condition_${Date.now()}`,
        x: 520 + offset,
        y: 80,
      });
      setNodes((current) => [...current, node as FlowNode]);
      setSelectedNodeId(node.id);
      return;
    }
    if (kind === "approval") {
      const node = buildApprovalBuilderNode({
        id: `node_approval_${Date.now()}`,
        x: 520 + offset,
        y: 150,
      });
      setNodes((current) => [...current, node as FlowNode]);
      setSelectedNodeId(node.id);
      return;
    }
    const node = buildEndBuilderNode({ id: `node_end_${Date.now()}`, x: 720 + offset, y: 260 });
    setNodes((current) => [...current, node as FlowNode]);
    setSelectedNodeId(node.id);
  }

  function deleteSelectedNode() {
    if (!selectedNodeId) {
      return;
    }
    setNodes((current) => current.filter((node) => node.id !== selectedNodeId));
    setEdges((current) => current.filter((edge) => edge.source !== selectedNodeId && edge.target !== selectedNodeId));
    setSelectedNodeId(null);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const created = await createWorkflow(formValues);
      setMessage(`已创建 ${created.name}`);
      await reloadWorkflows(created.id);
      setCreatePanelOpen(false);
    });
  }

  async function handlePublish() {
    if (!selectedWorkflowId) {
      return;
    }
    await run(async () => {
      const graph = builderGraphToWorkflowGraph(nodes as BuilderNode[], edges);
      const version = await publishWorkflowVersion(selectedWorkflowId, graph);
      setMessage(`已发布可视化工作流版本 ${version.version_number}`);
      await loadWorkflowDetail(selectedWorkflowId);
      await reloadWorkflows(selectedWorkflowId);
    });
  }

  async function handleCreateRun() {
    if (!selectedWorkflowId) {
      return;
    }
    await run(async () => {
      const input = parseRunInput(runInputText);
      const run = await createWorkflowRun(selectedWorkflowId, input);
      setLastRun(run);
      setMessage(`运行已排队：${run.id}`);
      applyRunStatuses(run);
    });
  }

  async function handleExecuteRun() {
    if (!lastRun) {
      return;
    }
    await run(async () => {
      const run = await executeRun(lastRun.id);
      setLastRun(run);
      setMessage(`运行 ${statusLabel(run.status)}`);
      applyRunStatuses(run);
    });
  }

  function applyRunStatuses(run: WorkflowRun) {
    const statuses = mapRunStepsToNodeStatus(run.steps);
    setNodes((current) => applyNodeStatuses(current as BuilderNode[], statuses));
  }

  function updateSelectedNodeData(nextData: Partial<BuilderNodeData>) {
    if (!selectedNodeId) {
      return;
    }
    setNodes((current) =>
      current.map((node) =>
        node.id === selectedNodeId
          ? {
              ...node,
              data: { ...node.data, ...nextData },
            }
          : node,
      ),
    );
  }

  function updateSelectedNodeConfig(nextConfig: Record<string, unknown>) {
    if (!selectedNode) {
      return;
    }
    updateSelectedNodeData({ config: { ...selectedNode.data.config, ...nextConfig } });
  }

  function updateSelectedNodeInputMapping(nextInputMapping: Record<string, unknown>) {
    updateSelectedNodeData({ input_mapping: nextInputMapping });
  }

  const currentWorkflow = workflows.find((w) => w.id === selectedWorkflowId) ?? null;

  return (
    <div className="space-y-5">
      {/* Header */}
      <header className="border-b border-line pb-4">
        <h1 className="text-page-title text-ink">工作流</h1>
        <p className="mt-1 text-sm text-ink-3">编排、发布并执行可视化的智能体工作流。</p>
      </header>

      {message ? <MessageBanner message={message} /> : null}

      {/* Compact workflow selector bar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <button
            className="inline-flex min-h-9 items-center gap-2 rounded-xl border border-line bg-surface-solid px-4 text-sm font-medium text-ink-2 transition-colors hover:border-line-strong hover:bg-surface"
            onClick={() => setWorkflowDropdownOpen((v) => !v)}
            type="button"
          >
            <span>{currentWorkflow ? currentWorkflow.name : "选择工作流"}</span>
            <ChevronDown size={14} />
          </button>
          {workflowDropdownOpen ? (
            <div className="absolute left-0 top-full z-40 mt-1 w-72 overflow-hidden rounded-xl border border-line bg-surface-solid shadow-float">
              <div className="max-h-64 overflow-auto p-1">
                {workflows.length === 0 ? (
                  <div className="px-3 py-4 text-sm text-ink-3">暂无工作流，请先创建</div>
                ) : (
                  workflows.map((workflow) => (
                    <button
                      className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                        selectedWorkflowId === workflow.id
                          ? "bg-accent/10 text-accent"
                          : "text-ink-2 hover:bg-surface"
                      }`}
                      key={workflow.id}
                      onClick={() => {
                        setSelectedWorkflowId(workflow.id);
                        setWorkflowDropdownOpen(false);
                      }}
                      type="button"
                    >
                      <span className="font-medium">{workflow.name}</span>
                      <span className="text-xs text-ink-3">
                        v{workflow.current_version?.version_number ?? "-"}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          ) : null}
        </div>

        {currentWorkflow ? (
          <div className="flex items-center gap-2 text-xs text-ink-3">
            <span>v{currentWorkflow.current_version?.version_number ?? "-"}</span>
            <span>·</span>
            <span>{currentWorkflow.current_version?.graph.nodes.length ?? 0} nodes</span>
            <span>·</span>
            <StatusPill status={currentWorkflow.status} tone={statusTone(currentWorkflow.status)} size="sm" />
          </div>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          <Button variant="default" disabled={busy} onClick={() => void loadInitialData()} type="button">
            刷新
          </Button>
          <Button variant="default" disabled={busy} onClick={() => setCreatePanelOpen((v) => !v)} type="button">
            <Plus size={14} />
            新建
          </Button>
        </div>
      </div>

      {/* Inline create form */}
      {createPanelOpen ? (
        <Card as="form" className="space-y-4 p-5" onSubmit={handleCreate}>
          <div className="flex items-center justify-between">
            <h2 className="text-section-title text-ink">新建工作流</h2>
            <Button variant="primary" disabled={busy} type="submit">
              创建
            </Button>
          </div>
          <Field label="Name">
            <input
              className="field-input"
              onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
              value={formValues.name}
            />
          </Field>
          <Field label="Description">
            <textarea
              className="field-input min-h-20 resize-y"
              onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
              value={formValues.description}
            />
          </Field>
        </Card>
      ) : null}

      {/* Full-width canvas area */}
      <Card className="relative overflow-hidden" >
        <div className="h-[680px]">
          <ReactFlow
            edges={edges}
            fitView
            nodeTypes={nodeTypes}
            nodes={nodes}
            onConnect={onConnect}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onNodesChange={onNodesChange}
          >
            <MiniMap pannable zoomable />
            <Controls />
            <Background />
          </ReactFlow>
        </div>

        {/* Floating node toolbar at the bottom */}
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center p-4">
          <div className="pointer-events-auto flex flex-wrap items-center gap-2 rounded-2xl border border-line bg-surface/80 px-4 py-2.5 shadow-card backdrop-blur-xl">
            <span className="mr-1 text-xs font-medium text-ink-3">{nodes.length} 节点 · {edges.length} 边</span>
            <div className="mx-1 h-4 w-px bg-line" aria-hidden />
            <Button variant="ghost" disabled={busy} onClick={() => loadTemplateGraph()} type="button">
              模板
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("agent")} type="button">
              <Plus size={13} /> 智能体
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("retrieval")} type="button">
              <Plus size={13} /> 检索
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("tool")} type="button">
              <Plus size={13} /> 工具
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("condition")} type="button">
              <Plus size={13} /> Condition
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("approval")} type="button">
              <Plus size={13} /> 审批
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => addNode("end")} type="button">
              <Plus size={13} /> 结束
            </Button>
            <div className="mx-1 h-4 w-px bg-line" aria-hidden />
            <Button variant="danger" disabled={busy || !selectedNodeId} onClick={deleteSelectedNode} type="button">
              <Trash2 size={13} /> 删除
            </Button>
            <Button variant="primary" disabled={busy || !selectedWorkflowId} onClick={handlePublish} type="button">
              <Upload size={13} /> 发布
            </Button>
          </div>
        </div>
      </Card>

      {/* Run panel + JSON preview row */}
      <div className="grid gap-5 lg:grid-cols-2">
        {/* Run panel */}
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-section-title text-ink">运行</h2>
            <div className="flex gap-2">
              <Button variant="primary" disabled={busy || !selectedWorkflowId} onClick={handleCreateRun} type="button">
                <Play size={13} /> 排队
              </Button>
              <Button variant="default" disabled={busy || !lastRun} onClick={handleExecuteRun} type="button">
                <Play size={13} /> 执行
              </Button>
            </div>
          </div>
          <Field label="运行输入 JSON">
            <textarea
              className="field-input min-h-28 resize-y font-mono text-xs"
              onChange={(event) => setRunInputText(event.target.value)}
              value={runInputText}
            />
          </Field>
          {lastRun ? (
            <div className="rounded-xl border border-success/30 bg-success/10 p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-xs font-semibold uppercase tracking-wide text-success">最近运行</div>
                <span className="text-xs font-medium text-success">{statusLabel(lastRun.status)}</span>
              </div>
              <div className="mt-1 text-xs text-success">
                {lastRun.steps.length} steps · {lastRun.tool_calls.length} tool calls
              </div>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-xs text-ink">
                {JSON.stringify(lastRun.output ?? lastRun.input, null, 2)}
              </pre>
            </div>
          ) : null}
        </Card>

        {/* Collapsible JSON preview */}
        <Card className="overflow-hidden p-5">
          <button
            className="flex w-full items-center justify-between text-left"
            onClick={() => setJsonPreviewOpen((v) => !v)}
            type="button"
          >
            <div className="flex items-center gap-2">
              <Eye size={14} className="text-ink-3" />
              <h2 className="text-section-title text-ink">流程图 JSON</h2>
            </div>
            <ChevronDown
              size={16}
              className={`text-ink-3 transition-transform ${jsonPreviewOpen ? "rotate-180" : ""}`}
            />
          </button>
          {jsonPreviewOpen ? (
            <pre className="mt-4 max-h-80 overflow-auto rounded-xl border border-line bg-surface-solid p-3 text-xs text-ink-2">
              {graphPreview}
            </pre>
          ) : (
            <p className="mt-2 text-xs text-ink-3">点击展开查看完整流程图 JSON 定义</p>
          )}
        </Card>
      </div>

      {/* Node config Sheet */}
      <Sheet
        open={!!selectedNode}
        onClose={() => setSelectedNodeId(null)}
        title={selectedNode ? `节点配置 · ${selectedNode.data.label}` : "节点配置"}
        side="right"
      >
        {selectedNode ? (
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-ink-3">{selectedNode.id}</p>
              <span className="rounded-md border border-line px-2.5 py-1 text-xs font-medium text-ink-2">
                {statusLabel(selectedNode.data.nodeType)}
              </span>
            </div>

            <Field label="标签">
              <input
                className="field-input"
                onChange={(event) => updateSelectedNodeData({ label: event.target.value })}
                value={selectedNode.data.label}
              />
            </Field>

            {selectedNode.data.nodeType === "agent" ? (
              <>
                <Field label="智能体版本">
                  <select
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ agent_version_id: event.target.value })}
                    value={String(selectedNode.data.config.agent_version_id ?? "")}
                  >
                    <option value="">请选择智能体版本</option>
                    {agents.map((agent) => (
                      <option disabled={!agent.current_version_id} key={agent.id} value={agent.current_version_id ?? ""}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="指令">
                  <textarea
                    className="field-input min-h-24 resize-y"
                    onChange={(event) => updateSelectedNodeConfig({ instruction: event.target.value })}
                    value={String(selectedNode.data.config.instruction ?? "")}
                  />
                </Field>
              </>
            ) : null}

            {selectedNode.data.nodeType === "retrieval" ? (
              <>
                <Field label="知识库">
                  <select
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ knowledge_base_ids: event.target.value ? [event.target.value] : [] })}
                    value={String((selectedNode.data.config.knowledge_base_ids as string[] | undefined)?.[0] ?? "")}
                  >
                    <option value="">请选择知识库</option>
                    {knowledgeBases.map((knowledgeBase) => (
                      <option key={knowledgeBase.id} value={knowledgeBase.id}>
                        {knowledgeBase.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Top K">
                  <input
                    className="field-input"
                    max="20"
                    min="1"
                    onChange={(event) => updateSelectedNodeConfig({ top_k: Number.parseInt(event.target.value, 10) || 5 })}
                    type="number"
                    value={String(selectedNode.data.config.top_k ?? 5)}
                  />
                </Field>
              </>
            ) : null}

            {selectedNode.data.nodeType === "tool" ? (
              <>
                <Field label="智能体">
                  <select
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ agent_id: event.target.value })}
                    value={String(selectedNode.data.config.agent_id ?? "")}
                  >
                    <option value="">请选择智能体</option>
                    {agents.map((agent) => (
                      <option key={agent.id} value={agent.id}>
                        {agent.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="工具">
                  <select
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ tool_id: event.target.value })}
                    value={String(selectedNode.data.config.tool_id ?? "")}
                  >
                    <option value="">请选择工具</option>
                    {tools.map((tool) => (
                      <option disabled={tool.status !== "active"} key={tool.id} value={tool.id}>
                        {tool.display_name || tool.name} · {tool.risk_level}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="审批标题">
                  <input
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ approval_title: event.target.value })}
                    value={String(selectedNode.data.config.approval_title ?? "")}
                  />
                </Field>
                <Field label="审批说明">
                  <textarea
                    className="field-input min-h-20 resize-y"
                    onChange={(event) => updateSelectedNodeConfig({ approval_instructions: event.target.value })}
                    value={String(selectedNode.data.config.approval_instructions ?? "")}
                  />
                </Field>
              </>
            ) : null}

            {selectedNode.data.nodeType === "approval" ? (
              <>
                <Field label="审批标题">
                  <input
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ title: event.target.value })}
                    value={String(selectedNode.data.config.title ?? "")}
                  />
                </Field>
                <Field label="指令">
                  <textarea
                    className="field-input min-h-24 resize-y"
                    onChange={(event) => updateSelectedNodeConfig({ instructions: event.target.value })}
                    value={String(selectedNode.data.config.instructions ?? "")}
                  />
                </Field>
                <Field label="风险等级">
                  <select
                    className="field-input"
                    onChange={(event) => updateSelectedNodeConfig({ risk_level: event.target.value })}
                    value={String(selectedNode.data.config.risk_level ?? "medium")}
                  >
                    <option value="low">低</option>
                    <option value="medium">中</option>
                    <option value="high">高</option>
                    <option value="critical">严重</option>
                  </select>
                </Field>
              </>
            ) : null}

            <Field label="输入映射 JSON">
              <textarea
                className="field-input min-h-28 resize-y font-mono"
                onChange={(event) => {
                  try {
                    updateSelectedNodeInputMapping(JSON.parse(event.target.value) as Record<string, unknown>);
                  } catch {
                    setMessage("输入映射必须是合法的 JSON");
                  }
                }}
                value={JSON.stringify(selectedNode.data.input_mapping ?? {}, null, 2)}
              />
            </Field>
          </div>
        ) : null}
      </Sheet>
    </div>
  );
}

function WorkflowNodeCard({ data, selected }: NodeProps<Node<BuilderNodeData>>) {
  const tone = statusTone(data.status);
  const borderColor = nodeBorderColor[data.nodeType] ?? "border-l-ink-3";
  return (
    <div
      className={`min-w-44 rounded-xl border border-l-[3px] bg-surface-solid px-3 py-2.5 shadow-soft ${borderColor} ${
        selected ? "border-accent ring-2 ring-accent-soft" : "border-line"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-ink">{data.label}</div>
        <span className={`rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase ${nodeToneClass[tone]}`}>
          {statusLabel(data.status ?? data.nodeType)}
        </span>
      </div>
      <div className="mt-1 text-xs text-ink-3">{statusLabel(data.nodeType)}</div>
    </div>
  );
}
