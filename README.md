# AI Study Assistant

本地优先的 RAG 学习助手，把学习资料转化为可问答、可引用、可复习的个人知识库。

## 核心特性

- **资料即知识库**：上传 PDF/Markdown/TXT，自动解析、分块、建立向量索引
- **问答有据可依**：每个回答标注来源文档、页码、chunk 编号，点击查看原文
- **混合检索**：ChromaDB 向量召回 + SQLite FTS5 关键词召回，通过 RRF 融合排序
- **Multi-Agent 智能路由**：Supervisor 自动判断意图，分配给 Tutor/Examiner/Summarizer
- **知识图谱可视化**：自动提取概念和关系，D3.js 交互式展示
- **学习闭环**：上传 → 提问 → 测验 → 错题复习 → Anki 导出
- **数据完全本地**：所有数据保存在本地，隐私可控

## 功能一览

| 模块 | 功能 |
|------|------|
| 文档管理 | 上传(PDF/TXT/MD)、笔记创建、标签、AI摘要、知识库分组 |
| 智能问答 | RAG问答、多轮对话、查询重写、引用溯源、历史搜索 |
| 学习测验 | LLM出题、在线答题、错题记录、掌握度追踪、Anki导出 |
| 学习看板 | 统计概览、正确率分析、薄弱点识别、学习趋势 |
| 知识图谱 | 概念提取、关系分析、D3.js可视化、相关概念推荐 |
| Multi-Agent | Supervisor意图分类、Tutor/Examiner/Summarizer专业Agent |
| 工程化 | 一键备份/恢复、Markdown导出、Debug Panel |

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+
- OpenAI API Key（或使用本地 Ollama）

### 1. 后端

```bash
cd backend

# 创建虚拟环境
python3.12 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 OPENAI_API_KEY

# 启动后端
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

后端启动后访问 http://localhost:8000/docs 查看 API 文档。

### 2. 前端

```bash
cd frontend

# 安装依赖
npm install

# 启动前端开发服务器
npm run dev
```

前端启动后访问 http://localhost:5173

### 使用本地模型（可选）

本地 embedding 和 reranker 需要额外安装 PyTorch / sentence-transformers：

```bash
cd backend
pip install -r requirements-local.txt

# 修改 .env
ASA_EMBEDDING_PROVIDER=local
ASA_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
ASA_EMBEDDING_DIMENSION=512
```

如果不想使用云端 LLM API，可以用 Ollama 本地部署：

```bash
# 安装 Ollama: https://ollama.com
# 拉取模型
ollama pull qwen2.5:7b

# 修改 .env
ASA_LLM_PROVIDER=ollama
ASA_LLM_MODEL=qwen2.5:7b
ASA_OLLAMA_BASE_URL=http://localhost:11434/v1
```

## 项目结构

```
├── backend/                        Python FastAPI 后端
│   ├── app/
│   │   ├── main.py                 FastAPI 入口 + lifespan
│   │   ├── config.py               pydantic-settings 配置
│   │   ├── db/database.py          SQLite 初始化 + 21 张表
│   │   ├── models/schemas.py       Pydantic 模型
│   │   ├── services/
│   │   │   ├── parser.py           文档解析（PDF/TXT/MD）
│   │   │   ├── chunker.py          文本分块（段落感知 + overlap）
│   │   │   ├── embedder.py         Embedding 生成
│   │   │   ├── vectorstore.py      ChromaDB 向量存储
│   │   │   ├── retriever.py        Vector + FTS5 + RRF 混合检索
│   │   │   ├── generator.py        LLM 生成 + SSE streaming
│   │   │   ├── rag.py              RAG 流程编排（7步ingest）
│   │   │   ├── quality.py          Chunk 质量评分
│   │   │   ├── image_extractor.py  PDF 图片提取
│   │   │   ├── knowledge_graph.py  知识图谱构建
│   │   │   └── agents/             Multi-Agent 系统
│   │   │       ├── supervisor.py   Supervisor 意图路由
│   │   │       ├── tutor.py        深入解释 Agent
│   │   │       ├── examiner.py     测验生成 Agent
│   │   │       └── summarizer.py   文档摘要 Agent
│   │   └── routers/
│   │       ├── documents.py        文档管理 API
│   │       ├── chat.py             问答 API（SSE + FTS5搜索）
│   │       ├── collections.py      知识库分组 API
│   │       ├── backup.py           备份/恢复/MD导出 API
│   │       ├── quiz.py             测验/错题/Anki/看板 API
│   │       ├── knowledge_graph.py  知识图谱 API
│   │       └── multi_agent.py      Multi-Agent API
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/                       React + Vite + TypeScript 前端
│   ├── src/
│   │   ├── App.tsx                 路由 + 暗色侧边栏布局
│   │   ├── pages/
│   │   │   ├── Documents.tsx       文档管理（拖拽上传 + 彩色标签）
│   │   │   ├── Chat.tsx            智能问答（SSE + 智能模式开关）
│   │   │   ├── Quiz.tsx            学习测验（卡片选项 + 进度条）
│   │   │   ├── Dashboard.tsx       学习看板（渐变卡片 + 图表）
│   │   │   └── KnowledgeGraph.tsx  知识图谱（D3.js 力导向图）
│   │   └── api/index.ts            API 客户端（41个接口）
│   └── package.json
│
└── docs/
    ├── PRD.md                      产品需求文档（v3，全部 Phase ✅）
    ├── TECHNICAL_DESIGN.md         技术设计文档
    └── PROJECT_SUMMARY.md          项目完成总结
```

## 技术栈

**后端**：FastAPI + Python 3.12 + SQLite (WAL) + ChromaDB + OpenAI API + PyMuPDF  
**前端**：React 18 + TypeScript + Vite + TailwindCSS + D3.js + Recharts

## 数据存储

所有数据保存在 `~/.ai-study-assistant/` 目录：

```
~/.ai-study-assistant/
├── data/
│   ├── documents/     # 原始文件
│   ├── chroma_db/     # 向量索引 (HNSW)
│   ├── chunk_images/  # PDF 提取的图片
│   └── app.db         # SQLite 数据库 (21 张表)
```

## 开发阶段

| Phase | 内容 | 状态 |
|-------|------|------|
| 1 | MVP：文档上传 + RAG 问答 + 引用溯源 + Debug Panel | ✅ |
| 2 | 多轮对话 + query rewrite + 笔记总结 + 标签分类 | ✅ |
| 2.5 | 知识库分组 + 备份恢复 + Markdown 导出 | ✅ |
| 3 | 测验生成 + 错题本 + Anki 导出 + 学习看板 | ✅ |
| 4 | 混合检索 + FTS5 历史搜索 + Chunk 质量评分 + PDF 图片提取 | ✅ |
| 5 | 知识图谱（NER + 共现分析 + D3.js 可视化） | ✅ |
| 6 | Multi-Agent（Supervisor + Tutor/Examiner/Summarizer） | ✅ |

详细需求见 [docs/PRD.md](docs/PRD.md)。

## API 端点

后端共提供 30+ 个 REST API 端点：

- **文档管理**：上传、列表、删除、标签、摘要、图片
- **知识库**：创建、列表、删除、文档分配
- **问答**：SSE 聊天、会话管理、历史搜索
- **测验**：生成、提交、错题、复习、Anki 导出、看板
- **知识图谱**：构建、查询、相关概念
- **Multi-Agent**：智能路由对话
- **备份**：导出、导入、Markdown 导出

## 开发工具

### 后端

```bash
cd backend
source venv/bin/activate

# Lint 检查
ruff check app/

# 格式化
ruff format app/

# 类型检查
mypy app/

# 运行测试
pytest tests/ -v
```

### 检索质量评测

复制示例 JSONL，并把相关文档名、文档 ID 或 chunk ID 替换为真实标注：

```bash
cd backend
cp eval/retrieval.example.jsonl eval/retrieval.jsonl

# 同时比较纯向量检索和混合检索
python -m app.evaluation.retrieval \
  --dataset eval/retrieval.golden.jsonl \
  --modes vector hybrid \
  --k 1 3 5 \
  --output /tmp/retrieval-report.json \
  --summary-output eval/retrieval.baseline.summary.json
```

命令输出 `Hit@K`、`MRR`、`Recall@K`、无答案拒答准确率和检索延迟。评测只运行召回层，不调用回答生成模型。完整报告可能包含本地文档名，建议输出到临时目录；摘要报告不含逐条召回结果，可以提交到仓库。

当前黄金集、基线结果和质量门槛见 [docs/EVALUATION.md](docs/EVALUATION.md)。

### 前端

```bash
cd frontend

# ESLint 检查
npm run lint

# Prettier 格式化
npm run format

# 运行测试
npm run test
```

### CI/CD

项目使用 GitHub Actions 进行持续集成，每次 push 到 main 或 PR 时自动运行：

- **后端**：ruff lint → ruff format → mypy → pytest
- **前端**：ESLint → Prettier → Vitest → Production Build

详见 [.github/workflows/ci.yml](.github/workflows/ci.yml)。

## License

MIT
