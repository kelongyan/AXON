# AXON

> ◈ 面向企业级 AI 应用的多智能体协作平台。

AXON 是一个以 **Agent 编排、工具调用、知识库增强、流程治理与质量评估** 为核心的多智能体工作台。项目当前阶段聚焦于可运行、可扩展、可验证的工程底座：后端提供稳定 API 与任务编排能力，前端提供统一控制台，基础设施通过 Docker Compose 一键拉起。

当前项目全程通过 **大模型 API** 使用模型能力，支持 OpenAI 兼容格式的模型提供商；暂不做本地模型部署、GPU 推理容器、模型权重管理或本地推理服务集成。

## ✦ 核心能力

| 模块 | 能力 |
| --- | --- |
| ✦ Agent | 智能体配置、角色设定、模型参数、运行上下文 |
| ✦ Tools | 工具注册、工具执行、输入输出约束、调用审计 |
| ✦ Workflows | 多节点流程编排、运行实例、步骤状态、错误追踪 |
| ✦ Knowledge Bases | 文档知识库、向量化检索、Embedding API 接入 |
| ✦ Evaluations | 评测任务、样本管理、运行记录、质量反馈 |
| ✦ Governance | API 鉴权、执行记录、依赖就绪检查、服务健康监控 |

## ◇ 技术栈

- **Backend**：FastAPI · SQLAlchemy · Alembic · Pydantic
- **Frontend**：Next.js · React · TypeScript · Vitest
- **Data**：PostgreSQL + pgvector · Redis · MinIO
- **Runtime**：Docker Compose · API Worker
- **Model Access**：OpenAI-compatible Chat Completions · Embeddings API

## ✧ 项目结构

```text
AXON
├─ apps
│  ├─ api          # FastAPI 服务、数据库模型、迁移、领域服务与测试
│  └─ web          # Next.js 控制台、模块页面、前端数据访问与测试
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## ⬡ 快速启动

```powershell
Copy-Item .env.example .env
docker compose up --build
```

启动后可访问：

| 服务 | 地址 |
| --- | --- |
| AXON Console | `http://localhost:3000` |
| API Health | `http://localhost:8000/health` |
| API Readiness | `http://localhost:8000/health/ready` |
| MinIO Console | `http://localhost:9001` |

## ✦ 模型 API 配置

在 `.env` 中配置兼容 OpenAI 格式的模型提供商：

```powershell
AGENTFLOW_LLM_API_BASE_URL=https://api.openai.com/v1
AGENTFLOW_LLM_API_KEY=
AGENTFLOW_LLM_MODEL=gpt-4.1-mini

AGENTFLOW_EMBEDDING_API_BASE_URL=
AGENTFLOW_EMBEDDING_API_KEY=
AGENTFLOW_EMBEDDING_MODEL=text-embedding-3-small
```

说明：

- `AGENTFLOW_LLM_*` 用于对话、规划、智能体推理等能力。
- `AGENTFLOW_EMBEDDING_*` 用于知识库向量化与语义检索。
- `.env` 只用于本地环境，禁止提交真实密钥。
- 前端环境变量只放控制台访问配置，不放模型供应商密钥。

## ◈ 后端开发

```powershell
Set-Location apps/api
python -m pip install -e ".[dev]"
python -m pytest
python -m alembic heads
```

## ◈ 前端开发

```powershell
Set-Location apps/web
npm install
npm test -- --run
npm run build
```

## ✧ 当前阶段

AXON 当前处于第一轮产品骨架与核心模块建设阶段，已覆盖：

- 基础服务编排与健康检查
- Agent / Tools / Workflows / Knowledge Bases / Evaluations 基础 API
- 多模块控制台页面
- PostgreSQL、Redis、MinIO、pgvector 集成
- LLM 与 Embedding 的 API-only 接入策略

## ✦ 安全约定

- 不提交 `.env`、真实 API Key、供应商凭据或本地密钥。
- 不提交方案书、过程文档、运行输出、缓存目录和构建产物。
- 生产环境必须配置独立鉴权密钥、数据库凭据和对象存储凭据。

---

**AXON** · 让智能体从“会回答”走向“能协作、可治理、可交付”。
