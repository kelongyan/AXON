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
import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { type Agent, fetchAgents } from "@/lib/agents";
import { type KnowledgeBase, fetchKnowledgeBases } from "@/lib/knowledge-bases";
import {
  type BuilderNode,
  type BuilderNodeData,
  applyNodeStatuses,
  buildApprovalBuilderNode,
  buildAgentBuilderNode,
  buildDefaultBuilderGraph,
  buildEndBuilderNode,
  buildRetrievalBuilderNode,
  buildStartBuilderNode,
  builderGraphToWorkflowGraph,
  mapRunStepsToNodeStatus,
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

const defaultWorkflowForm: WorkflowFormValues = {
  name: "Visual RAG Workflow",
  description: "Phase 6 visual workflow builder flow.",
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

export function WorkflowsConsole() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [formValues, setFormValues] = useState<WorkflowFormValues>(defaultWorkflowForm);
  const [runInputText, setRunInputText] = useState(defaultRunInput);
  const [lastRun, setLastRun] = useState<WorkflowRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<FlowNode>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<FlowEdge>([]);

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
    await runAction(async () => {
      const [nextAgents, nextWorkflows, nextKnowledgeBases] = await Promise.all([
        fetchAgents(),
        fetchWorkflows(),
        fetchKnowledgeBases(),
      ]);
      setAgents(nextAgents);
      setWorkflows(nextWorkflows);
      setKnowledgeBases(nextKnowledgeBases);
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
      setMessage("Create an Agent with a published version before loading the template");
      return;
    }
    const graph = buildDefaultBuilderGraph(agentVersionId);
    setNodes(graph.nodes as FlowNode[]);
    setEdges(graph.edges as FlowEdge[]);
    setSelectedNodeId(graph.nodes[0]?.id ?? null);
    setMessage("Loaded visual Start -> Agent -> End template");
  }

  function addNode(kind: "agent" | "retrieval" | "approval" | "end") {
    const offset = nodes.length * 45;
    if (kind === "agent") {
      const agentVersionId = selectedAgent?.current_version_id;
      if (!agentVersionId) {
        setMessage("Select or create an Agent before adding an Agent node");
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
    await runAction(async () => {
      const created = await createWorkflow(formValues);
      setMessage(`Created ${created.name}`);
      await reloadWorkflows(created.id);
    });
  }

  async function handlePublish() {
    if (!selectedWorkflowId) {
      return;
    }
    await runAction(async () => {
      const graph = builderGraphToWorkflowGraph(nodes as BuilderNode[], edges);
      const version = await publishWorkflowVersion(selectedWorkflowId, graph);
      setMessage(`Published visual workflow version ${version.version_number}`);
      await loadWorkflowDetail(selectedWorkflowId);
      await reloadWorkflows(selectedWorkflowId);
    });
  }

  async function handleCreateRun() {
    if (!selectedWorkflowId) {
      return;
    }
    await runAction(async () => {
      const input = parseRunInput(runInputText);
      const run = await createWorkflowRun(selectedWorkflowId, input);
      setLastRun(run);
      setMessage(`Run queued: ${run.id}`);
      applyRunStatuses(run);
    });
  }

  async function handleExecuteRun() {
    if (!lastRun) {
      return;
    }
    await runAction(async () => {
      const run = await executeRun(lastRun.id);
      setLastRun(run);
      setMessage(`Run ${run.status}`);
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

  async function runAction(action: () => Promise<void>) {
    try {
      setBusy(true);
      setMessage(null);
      await action();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="border-b border-zinc-200 pb-5">
        <p className="text-xs font-semibold uppercase tracking-normal text-teal-700">Visual Workflow Builder</p>
        <div className="mt-2 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-zinc-950">Workflows</h1>
            <p className="mt-1 text-sm text-zinc-500">Build, publish, and execute visual Agent workflows.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <StatusPill label="Phase" value="6" tone="ready" />
            <StatusPill label="Canvas" value="React Flow" tone="ready" />
            <StatusPill label="Runtime" value="Sequential MVP" tone="ready" />
          </div>
        </div>
      </section>

      {message ? (
        <div className="rounded-md border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700">{message}</div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[280px_minmax(0,1fr)_380px]">
        <div className="space-y-5">
          <div className="rounded-lg border border-zinc-200 bg-white">
            <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
              <div>
                <div className="text-sm font-semibold text-zinc-950">Workflow List</div>
                <div className="mt-1 text-xs text-zinc-500">{workflows.length} configured</div>
              </div>
              <button className="control-button" disabled={busy} onClick={() => void loadInitialData()} type="button">
                Refresh
              </button>
            </div>
            <div className="max-h-[340px] overflow-auto p-2">
              {workflows.length === 0 ? (
                <div className="px-3 py-6 text-sm text-zinc-500">Create a workflow to start</div>
              ) : (
                workflows.map((workflow) => (
                  <button
                    className={`mb-2 w-full rounded-md border px-3 py-3 text-left transition ${
                      selectedWorkflowId === workflow.id
                        ? "border-teal-500 bg-teal-50 text-teal-950"
                        : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                    }`}
                    key={workflow.id}
                    onClick={() => setSelectedWorkflowId(workflow.id)}
                    type="button"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-sm font-medium">{workflow.name}</span>
                      <span className="text-xs capitalize">{workflow.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">
                      v{workflow.current_version?.version_number ?? "-"} · {workflow.current_version?.graph.nodes.length ?? 0} nodes
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>

          <form className="rounded-lg border border-zinc-200 bg-white p-4" onSubmit={handleCreate}>
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-zinc-950">Workflow</h2>
              <button className="control-button primary" disabled={busy} type="submit">
                Create
              </button>
            </div>
            <Field className="mt-4" label="Name">
              <input
                className="field-input"
                onChange={(event) => setFormValues({ ...formValues, name: event.target.value })}
                value={formValues.name}
              />
            </Field>
            <Field className="mt-4" label="Description">
              <textarea
                className="field-input min-h-20 resize-y"
                onChange={(event) => setFormValues({ ...formValues, description: event.target.value })}
                value={formValues.description}
              />
            </Field>
          </form>

          <div className="rounded-lg border border-zinc-200 bg-white p-4">
            <h2 className="text-base font-semibold text-zinc-950">Palette</h2>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button className="control-button" disabled={busy} onClick={() => loadTemplateGraph()} type="button">
                Template
              </button>
              <button className="control-button" disabled={busy} onClick={() => addNode("agent")} type="button">
                Agent
              </button>
              <button className="control-button" disabled={busy} onClick={() => addNode("retrieval")} type="button">
                Retrieval
              </button>
              <button className="control-button" disabled={busy} onClick={() => addNode("approval")} type="button">
                Approval
              </button>
              <button className="control-button" disabled={busy} onClick={() => addNode("end")} type="button">
                End
              </button>
            </div>
            <p className="mt-3 text-xs text-zinc-500">Tool and Condition nodes remain planned for a later runtime phase.</p>
          </div>
        </div>

        <div className="min-h-[760px] overflow-hidden rounded-lg border border-zinc-200 bg-white">
          <div className="flex items-center justify-between gap-3 border-b border-zinc-200 px-4 py-3">
            <div>
              <h2 className="text-base font-semibold text-zinc-950">Canvas</h2>
              <p className="mt-1 text-xs text-zinc-500">{nodes.length} nodes · {edges.length} edges</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="control-button" disabled={busy || !selectedNodeId} onClick={deleteSelectedNode} type="button">
                Delete Node
              </button>
              <button className="control-button primary" disabled={busy || !selectedWorkflowId} onClick={handlePublish} type="button">
                Publish
              </button>
            </div>
          </div>
          <div className="h-[704px]">
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
        </div>

        <div className="space-y-5">
          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-zinc-950">Node Config</h2>
                <p className="mt-1 text-xs text-zinc-500">{selectedNode?.id ?? "Select a node"}</p>
              </div>
              <span className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600">
                {selectedNode?.data.nodeType ?? "none"}
              </span>
            </div>
            {selectedNode ? (
              <div className="mt-4 space-y-4">
                <Field label="Label">
                  <input
                    className="field-input"
                    onChange={(event) => updateSelectedNodeData({ label: event.target.value })}
                    value={selectedNode.data.label}
                  />
                </Field>
                {selectedNode.data.nodeType === "agent" ? (
                  <>
                    <Field label="Agent Version">
                      <select
                        className="field-input"
                        onChange={(event) => updateSelectedNodeConfig({ agent_version_id: event.target.value })}
                        value={String(selectedNode.data.config.agent_version_id ?? "")}
                      >
                        <option value="">Select Agent Version</option>
                        {agents.map((agent) => (
                          <option disabled={!agent.current_version_id} key={agent.id} value={agent.current_version_id ?? ""}>
                            {agent.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Instruction">
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
                    <Field label="Knowledge Base">
                      <select
                        className="field-input"
                        onChange={(event) => updateSelectedNodeConfig({ knowledge_base_ids: event.target.value ? [event.target.value] : [] })}
                        value={String((selectedNode.data.config.knowledge_base_ids as string[] | undefined)?.[0] ?? "")}
                      >
                        <option value="">Select Knowledge Base</option>
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
                {selectedNode.data.nodeType === "approval" ? (
                  <>
                    <Field label="Approval Title">
                      <input
                        className="field-input"
                        onChange={(event) => updateSelectedNodeConfig({ title: event.target.value })}
                        value={String(selectedNode.data.config.title ?? "")}
                      />
                    </Field>
                    <Field label="Instructions">
                      <textarea
                        className="field-input min-h-24 resize-y"
                        onChange={(event) => updateSelectedNodeConfig({ instructions: event.target.value })}
                        value={String(selectedNode.data.config.instructions ?? "")}
                      />
                    </Field>
                    <Field label="Risk Level">
                      <select
                        className="field-input"
                        onChange={(event) => updateSelectedNodeConfig({ risk_level: event.target.value })}
                        value={String(selectedNode.data.config.risk_level ?? "medium")}
                      >
                        <option value="low">low</option>
                        <option value="medium">medium</option>
                        <option value="high">high</option>
                        <option value="critical">critical</option>
                      </select>
                    </Field>
                  </>
                ) : null}
                <Field label="Input Mapping JSON">
                  <textarea
                    className="field-input min-h-28 resize-y font-mono"
                    onChange={(event) => {
                      try {
                        updateSelectedNodeInputMapping(JSON.parse(event.target.value) as Record<string, unknown>);
                      } catch {
                        setMessage("Input mapping must be valid JSON");
                      }
                    }}
                    value={JSON.stringify(selectedNode.data.input_mapping ?? {}, null, 2)}
                  />
                </Field>
              </div>
            ) : (
              <div className="mt-4 text-sm text-zinc-500">Select a canvas node to configure it</div>
            )}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-zinc-950">Run</h2>
              <div className="flex gap-2">
                <button className="control-button primary" disabled={busy || !selectedWorkflowId} onClick={handleCreateRun} type="button">
                  Queue
                </button>
                <button className="control-button" disabled={busy || !lastRun} onClick={handleExecuteRun} type="button">
                  Execute
                </button>
              </div>
            </div>
            <textarea
              className="field-input mt-4 min-h-36 resize-y font-mono"
              onChange={(event) => setRunInputText(event.target.value)}
              value={runInputText}
            />
            {lastRun ? (
              <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-semibold uppercase tracking-normal text-emerald-700">Last Run</div>
                  <span className="text-xs font-medium text-emerald-700">{lastRun.status}</span>
                </div>
                <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap text-sm text-emerald-950">
                  {JSON.stringify(lastRun.output ?? lastRun.input, null, 2)}
                </pre>
              </div>
            ) : null}
          </section>

          <section className="rounded-lg border border-zinc-200 bg-white p-4">
            <h2 className="text-base font-semibold text-zinc-950">Graph JSON</h2>
            <pre className="mt-4 max-h-72 overflow-auto rounded-md border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-700">
              {graphPreview}
            </pre>
          </section>
        </div>
      </section>
    </div>
  );
}

function WorkflowNodeCard({ data, selected }: NodeProps<Node<BuilderNodeData>>) {
  const tone = statusTone(data.status);
  return (
    <div
      className={`min-w-44 rounded-md border bg-white px-3 py-2 shadow-sm ${
        selected ? "border-teal-500 ring-2 ring-teal-100" : "border-zinc-200"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-zinc-950">{data.label}</div>
        <span className={`rounded-sm px-1.5 py-0.5 text-[10px] font-semibold uppercase ${tone}`}>{data.status ?? data.nodeType}</span>
      </div>
      <div className="mt-1 text-xs text-zinc-500">{data.nodeType}</div>
    </div>
  );
}

function Field({
  children,
  className = "",
  label,
}: {
  children: ReactNode;
  className?: string;
  label: string;
}) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs font-semibold uppercase tracking-normal text-zinc-500">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function StatusPill({
  label,
  tone,
  value,
}: {
  label: string;
  tone: "neutral" | "ready";
  value: string;
}) {
  const toneClassName =
    tone === "ready" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-zinc-200 bg-white text-zinc-600";
  return (
    <span className={`rounded-md border px-2.5 py-1 font-medium ${toneClassName}`}>
      {label}: {value}
    </span>
  );
}

function statusTone(status?: string): string {
  if (status === "succeeded") {
    return "bg-emerald-50 text-emerald-700";
  }
  if (status === "running" || status === "queued") {
    return "bg-amber-50 text-amber-700";
  }
  if (status === "failed") {
    return "bg-rose-50 text-rose-700";
  }
  return "bg-zinc-100 text-zinc-600";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed";
}
