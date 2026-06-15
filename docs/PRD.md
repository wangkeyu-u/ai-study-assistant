## AI 学习助手 — 产品需求文档（工程落地版 v3）

> **当前进度：Phase 1 ✅ | Phase 2 ✅ | Phase 2.5 ✅ | Phase 3 ✅ | Phase 4 ✅ | Phase 5 ✅ | Phase 6 ✅ — 全部完成**
> 最后更新：2026-06-12

---

### 一、产品定位

**本地优先的 RAG 学习助手**，核心目标是把学习资料转化成可问答、可引用、可复习的个人知识库。

不做通用 AI 聊天工具，不做知识管理平台，只聚焦一件事：**让上传的学习资料变成随时可以提问、随时可以追溯原文的智能知识库。**

---

### 二、用户画像

个人使用的本地学习工具。使用者具备全栈开发能力，能够自行部署和维护。使用场景为自学技术文档、阅读论文教材、整理个人笔记时，需要一个"比全文搜索更智能、比 ChatGPT 更可靠"的本地知识问答系统。

---

### 三、核心价值

1. **资料即知识库**：上传 PDF/Markdown/TXT，系统自动解析、分块、建索引，无需手动整理。
2. **问答有据可依**：每个回答都标注来源文档、页码/段落、chunk 编号，点击跳转原文。
3. **不编造不臆测**：检索不到相关资料时明确告知"资料中没有找到足够依据"，杜绝幻觉。
4. **数据完全本地**：原始文件、向量索引、聊天记录全部保存在本地，隐私可控。

---

### 四、MVP 范围（Phase 1 ✅ 已完成）

#### 支持的资料类型

| 类型 | 格式 | 说明 |
|-----|------|------|
| PDF | `.pdf` | 文本型 PDF（不含扫描件 OCR） |
| 纯文本 | `.txt` | 直接读取 |
| Markdown | `.md` | 直接读取，保留标题层级 |
| 手动笔记 | 界面输入 | 用户在应用内直接粘贴/输入笔记内容 |

#### MVP 功能清单

| 功能 | 说明 |
|-----|------|
| 文档上传 | 拖拽或点击上传，支持批量 |
| 文档解析 | PDF 文字提取、TXT/MD 读取 |
| 文本分块 | 按段落 + 字数兜底的分块策略 |
| Embedding | 调用本地或云端嵌入模型生成向量 |
| 向量检索 | Top-K 相似度检索 |
| RAG 问答 | 检索结果 + 用户问题 → LLM 生成回答 |
| 引用溯源 | 回答附带文档名 + 页码/段落 + chunk 编号 |
| 文档管理 | 文档列表、删除文档（同步清理索引） |
| 本地存储 | SQLite 存元数据，ChromaDB 存向量 |
| 基础前端 | 文档管理页 + 问答页（两页即可） |

---

### 五、非 MVP 范围（明确不做）

以下功能在 MVP（Phase 1-2）阶段**不实现**，避免范围蔓延。部分功能已规划在后续阶段：

PPT 解析、Word 解析、网页抓取、视频字幕解析、OCR、复杂思维导图导出。（注：BM25 混合检索、Reranker、LangGraph、间隔重复、测验系统、Anki 导出、知识图谱、Multi-Agent 等已规划在 Phase 3-6。）

---

### 六、功能优先级

#### Must Have（MVP 必须）— ✅ 全部完成

- ✅ 文档上传（拖拽 + 点击，支持 PDF/TXT/MD）
- ✅ 文档解析（PDF 文字提取、纯文本读取）
- ✅ 文本分块（段落感知 + 固定长度兜底）
- ✅ Embedding 生成（本地模型或 OpenAI API）
- ✅ 向量检索（Top-K cosine similarity）
- ✅ RAG 问答（context + query → LLM 生成）
- ✅ 回答带引用来源（文档名、页码/段落、chunk 编号）
- ✅ 文档管理（列表、删除、索引同步清理）
- ✅ SQLite 本地存储（元数据 + 聊天记录）
- ✅ 基础前端界面（文档管理页 + 问答页）
- ✅ RAG Debug Panel（显示 query、top-k chunks、similarity score、prompt、token 消耗、生成耗时）
- ✅ 手动输入笔记（应用内简单文本框，保存为 note 类型文档）

#### Should Have（Phase 2-3）— Phase 2 ✅ 已完成，Phase 2.5 / Phase 3 待开发

- ✅ 多轮对话（上下文记忆，最近 10 条消息作为上下文窗口）
- ✅ 查询改写（query rewrite，LLM 改写上下文依赖型问题）
- ✅ 按主题/科目分类知识库（文档打标签，支持增删查）
- ✅ 简单学习笔记总结（对指定资料生成核心要点摘要）
- 知识库分组管理（多 Collection，按项目/科目隔离检索）← Phase 2.5
- 数据备份与导出（一键导出 zip，支持导入恢复）← Phase 2.5
- Markdown 导出回答（一键导出优质回答为 .md 文件）← Phase 2.5
- 基础测验生成（选择题 + 判断题）← Phase 3
- 错题记录（答错题目收集、重练）← Phase 3
- Anki 联动导出（将测验题 + 知识点导出为 Anki 卡片）← Phase 3
- 学习进度看板（统计上传量、知识覆盖率、问答频率、薄弱点）← Phase 3

#### Nice to Have（Phase 4-6）

- ✅ 混合检索（FTS5 + Vector + RRF）← Phase 4
- Reranker 重排序 ← Phase 4
- LangGraph 工作流编排 ← Phase 4
- 间隔重复复习（艾宾浩斯曲线）← Phase 3
- 知识点掌握度追踪 ← Phase 3
- 对话历史搜索（全文检索 + 语义搜索历史对话）← Phase 4
- Chunk 质量评分（信息密度评估，低质量 chunk 自动降权）← Phase 4
- PDF 图表提取（PyMuPDF 提取图片/表格作为 chunk 附加元数据）← Phase 4
- 跨文档知识关联（自动发现跨文档概念，构建知识图谱）← Phase 5
- 知识图谱可视化（关系图 + 概念节点 + 文档来源链接）← Phase 5
- Self-Reflective RAG（质量不达标自动重试）← Phase 4
- Multi-Agent 协作 ← Phase 6

---

### 七、系统架构

```
┌─────────────────────────────────────────────────┐
│              Tauri 桌面应用（React 前端）            │
│                                                   │
│   ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│   │ 文档管理页 │  │  问答页   │  │ RAG Debug 面板│  │
│   │ +标签管理 │  │ +会话侧栏 │  │               │  │
│   │ +AI摘要  │  │ +引用展示 │  │               │  │
│   └──────────┘  └──────────┘  └───────────────┘  │
└──────────────────────┬──────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────┐
│            Python FastAPI 后端                      │
│                                                   │
│   POST /api/documents/upload    文档上传           │
│   POST /api/documents/note      手动笔记【P2】     │
│   GET  /api/documents           文档列表           │
│   DELETE /api/documents/{id}    删除文档           │
│   POST /api/documents/{id}/tags 标签管理【P2】     │
│   POST /api/documents/{id}/summary AI摘要【P2】   │
│   POST /api/chat                RAG 问答（SSE）    │
│   GET  /api/chat/sessions       会话列表           │
│   DELETE /api/chat/sessions/{id} 删除会话          │
│   GET  /api/debug/last-query    上次查询 debug 信息│
│                                                   │
├───────────────────────────────────────────────────┤
│            RAG Pipeline（Phase 2 版）              │
│                                                   │
│   parse → chunk → embed → store                   │
│              ↓                                    │
│   query → rewrite【P2】 → embed → retrieve        │
│              ↓                                    │
│   build_prompt（+ history【P2】） → generate       │
│              ↓                                    │
│   extract citations → stream response (SSE)       │
└──────────────────────┬──────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐  ┌───────────┐  ┌──────────┐
   │ SQLite  │  │ ChromaDB  │  │ 本地文件  │
   │ 元数据   │  │ 向量索引   │  │ 原始文档  │
   │ +标签   │  │           │  │          │
   │ +消息   │  │           │  │          │
   └─────────┘  └───────────┘  └──────────┘
```

---

### 八、RAG 流程（MVP 版）

#### 8.1 索引流程（文档上传时触发）

```
用户上传文件
    │
    ▼
文件类型判断（PDF / TXT / MD）
    │
    ├── PDF → PyMuPDF 提取文字（按页）
    ├── TXT → 直接读取全文
    └── MD  → 读取全文，解析标题层级作为元数据
    │
    ▼
文本分块
    ├── 策略：按段落切分，单块目标 512 tokens
    ├── 重叠：相邻块重叠 64 tokens
    ├── 兜底：单段超过 1024 tokens 时按句子边界二次切分
    └── 元数据：每块携带 doc_id、chunk_index、page_num（如有）、heading（如有）
    │
    ▼
Embedding 生成
    ├── 本地模型：sentence-transformers/bge-small-zh-v1.5（默认）
    └── 云端备选：OpenAI text-embedding-3-small
    │
    ▼
存入 ChromaDB（向量 + 元数据）
写入 SQLite（文档元信息 + 分块统计）
```

#### 8.2 查询流程（用户提问时触发）

```
用户输入问题
    │
    ▼
【Phase 2】多轮对话上下文处理：
    ├── 从 SQLite 加载最近 10 条历史消息（5 轮对话）
    ├── 若历史消息 >= 2 条 → 触发 Query Rewrite
    │     LLM 将上下文依赖型问题改写为独立完整问题
    │     例："那第二章呢？" → "第二章的核心内容是什么？"
    └── 改写失败则回退使用原始问题
    │
    ▼
Query Embedding（同索引阶段使用的模型）
    │
    ▼
向量检索（ChromaDB top-K，默认 K=5）
    │
    ▼
相似度过滤：score < 0.3 的 chunk 丢弃
    │
    ├── 过滤后无结果 → 返回"资料中没有找到足够依据"
    │
    ▼
构建 Prompt：
    system: "你是一个学习助手。仅基于以下参考资料回答问题。
             如果资料中没有足够信息，请明确告知。
             每个回答必须标注引用来源，格式为 [N]。"
    context: 拼接 top-K chunks（编号标注）
    【Phase 2】history: 最近 10 条对话历史 + HISTORY_NOTE 说明
    user: 用户原始问题（注意：用原始问题而非改写后问题，让 LLM 直接回应用户意图）
    │
    ▼
LLM 生成回答（流式输出 SSE）
    │
    ▼
解析回答中的引用标记 [N]，关联到 chunks 表
    │
    ▼
返回：answer + citations[] + debug_info{}（含 rewritten_query 字段）
```

#### 8.3 RAG 质量控制规则

- **回答必须基于上传资料**：system prompt 强制约束，不允许使用模型自身知识回答。
- **每条回答必须有 citation**：回答中每个事实性陈述附带 `[文档名, 页码/段落, chunk_id]`。
- **检索不到资料时不编造**：相似度分数全部低于阈值（0.3）时，直接返回"资料中没有找到足够依据，建议上传相关资料或换一种问法"。
- **支持查看原文片段**：前端点击引用标记，展开对应 chunk 的原文内容。
- **RAG Debug Panel**：每次查询记录并展示以下调试信息：

| Debug 字段 | 说明 |
|-----------|------|
| `query` | 用户原始问题 |
| `query_embedding_model` | 使用的嵌入模型名 |
| `top_k_chunks` | 检索到的 chunk 列表（含文本摘要） |
| `similarity_scores` | 每个 chunk 的相似度分数 |
| `final_prompt` | 发送给 LLM 的完整 prompt |
| `token_usage` | prompt tokens + completion tokens |
| `generation_time_ms` | LLM 生成耗时（毫秒） |
| `retrieval_time_ms` | 检索耗时（毫秒） |

---

### 九、API 设计

#### 9.1 文档管理

```
POST   /api/documents/upload
  Body: multipart/form-data { file: File }
  Response: { id, filename, file_type, chunk_count, status, tags, created_at }
  Error:
    400 - 不支持的文件格式
    413 - 文件过大（>50MB）
    422 - PDF 无法解析 / 扫描版 PDF 无文字

POST   /api/documents/note
  Body: { title: string, content: string }
  Response: { id, filename, file_type, chunk_count, status, tags, created_at }
  说明: Phase 2 新增，手动笔记输入

GET    /api/documents
  Response: [{ id, filename, file_type, chunk_count, status, tags, created_at }]

DELETE /api/documents/{id}
  Response: { success: true, chunks_deleted: int }
  行为: 删除本地文件 + ChromaDB 中该 doc_id 的所有向量 + SQLite 元数据

GET    /api/documents/{id}/chunks
  Response: [{ chunk_id, text_preview, page_num, heading, chunk_index }]

POST   /api/documents/{id}/tags
  Body: { tag_name: string }
  Response: { success: true, tag: string }
  说明: Phase 2 新增，给文档添加标签（自动创建不存在的标签）

DELETE /api/documents/{id}/tags/{tag_name}
  Response: { success: true }
  说明: Phase 2 新增，移除文档的某个标签

GET    /api/documents/tags/all
  Response: [{ id, name, doc_count }]
  说明: Phase 2 新增，列出所有标签及其关联文档数

POST   /api/documents/{id}/summary
  Response: { doc_id, filename, summary }
  说明: Phase 2 新增，调用 LLM 生成文档核心要点摘要
```

#### 9.2 问答

```
POST   /api/chat
  Body: {
    session_id: string (可选，不传则新建会话),
    message: string
  }
  Response: SSE stream
    event: token     data: { text: string }            // 流式输出文本
    event: citation  data: { doc_name, page, chunk_id, text_preview }  // 引用信息
    event: debug     data: { ...debug_info }           // Debug 信息
    event: done      data: { message_id, citations_count }

GET    /api/chat/sessions
  Response: [{ id, title, message_count, created_at, updated_at }]

GET    /api/chat/sessions/{id}/messages
  Response: [{ role, content, citations[], created_at }]

DELETE /api/chat/sessions/{id}
  Response: { success: true }
```

#### 9.3 Debug

```
GET    /api/debug/last-query
  Response: {
    query: string,
    rewritten_query: string | null,    // Phase 2 新增：改写后的查询（如有）
    query_embedding_model: string,
    top_k_chunks: [{ chunk_id, text_preview, similarity_score, doc_name, page }],
    final_prompt: string,
    token_usage: { prompt_tokens, completion_tokens },
    retrieval_time_ms: number,
    generation_time_ms: number
  }
```

#### 9.4 知识库分组（Phase 2.5）

```
POST   /api/collections
  Body: { name: string, description?: string }
  Response: { id, name, description, doc_count, created_at }

GET    /api/collections
  Response: [{ id, name, description, doc_count, created_at }]

DELETE /api/collections/{id}
  Response: { success: true }
  行为: 删除分组但不删除文档（文档 collection_id 置 NULL）

PUT    /api/documents/{id}/collection
  Body: { collection_id: string | null }
  Response: { success: true }
```

#### 9.5 数据备份与导出（Phase 2.5）

```
POST   /api/backup/export
  Response: 下载 zip 文件（含 documents/ + chroma_db/ + app.db + config.json）

POST   /api/backup/import
  Body: multipart/form-data { file: zip }
  Response: { success: true, documents_restored: int }
  行为: 解压并恢复数据（覆盖前需确认）
```

#### 9.6 Markdown 导出回答（Phase 2.5）

```
POST   /api/chat/messages/{id}/export
  Response: 下载 .md 文件（含回答内容 + 引用来源列表）
```

#### 9.7 学习系统（Phase 3）

```
POST   /api/quiz/generate
  Body: { doc_ids?: string[], tag?: string, count?: int }
  Response: { quiz_id, questions: [{ id, type, text, options, correct_answer, explanation }] }

POST   /api/quiz/{quiz_id}/submit
  Body: { answers: [{ question_id, user_answer }] }
  Response: { correct_count, total, results: [{ question_id, correct, explanation }] }

GET    /api/quiz/wrong-answers
  Response: [{ id, question, user_answer, correct_answer, mastery_level, review_count }]

POST   /api/quiz/wrong-answers/{id}/review
  Response: { mastery_level, next_review }

GET    /api/anki/export
  Query: ?tag=xxx&doc_id=xxx&min_mastery=0
  Response: 下载 .csv 文件（Anki 兼容格式：正面 | 反面 | 标签）

GET    /api/dashboard
  Response: {
    total_documents: int,
    total_chunks: int,
    total_questions_asked: int,
    tag_stats: [{ tag, doc_count, question_count }],
    weak_points: [{ concept, mastery_score }],
    study_streak: int,
    recent_activity: [{ date, questions_count, docs_uploaded }]
  }
```

#### 9.8 对话历史搜索（Phase 4）

```
GET    /api/chat/search
  Query: ?q=关键词&mode=fulltext|semantic&limit=20
  Response: [{ session_id, message_id, role, content_preview, score, created_at }]
```

#### 9.9 知识图谱（Phase 5）

```
GET    /api/knowledge-graph
  Query: ?doc_id=xxx&min_weight=0.3
  Response: { nodes: [{ id, name, frequency, source_docs }], edges: [{ source, target, type, weight }] }

GET    /api/knowledge-graph/concepts
  Response: [{ id, name, frequency, description }]

GET    /api/knowledge-graph/related
  Query: ?concept_id=xxx&limit=5
  Response: [{ concept, weight, source_docs }]
```

---

### 十、数据库设计

#### 10.1 已实现的表（Phase 1 + Phase 2）

```sql
-- 文档表
CREATE TABLE documents (
    id            TEXT PRIMARY KEY,           -- UUID
    filename      TEXT NOT NULL,              -- 原始文件名
    file_type     TEXT NOT NULL,              -- 'pdf' | 'txt' | 'md' | 'note'
    file_path     TEXT NOT NULL,              -- 本地存储路径
    file_size     INTEGER NOT NULL,           -- 字节
    chunk_count   INTEGER DEFAULT 0,          -- 分块数量
    status        TEXT DEFAULT 'processing',  -- 'processing' | 'ready' | 'error'
    error_message TEXT,                       -- 处理失败时的错误信息
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文本块表
CREATE TABLE chunks (
    id            TEXT PRIMARY KEY,           -- UUID
    doc_id        TEXT NOT NULL REFERENCES documents(id),
    chunk_index   INTEGER NOT NULL,           -- 在文档中的序号
    text          TEXT NOT NULL,              -- 完整文本
    page_num      INTEGER,                    -- PDF 页码（TXT/MD 为 NULL）
    heading       TEXT,                       -- 所属标题（MD 解析）
    token_count   INTEGER NOT NULL,           -- token 估算
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_chunks_doc_id ON chunks(doc_id);

-- 标签表（Phase 2 新增）
CREATE TABLE tags (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文档-标签关联表（Phase 2 新增）
CREATE TABLE document_tags (
    doc_id        TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id        TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (doc_id, tag_id)
);

-- 聊天会话表
CREATE TABLE chat_sessions (
    id            TEXT PRIMARY KEY,           -- UUID
    title         TEXT NOT NULL,              -- 自动取第一条消息的前 30 字
    message_count INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 聊天消息表
CREATE TABLE chat_messages (
    id            TEXT PRIMARY KEY,           -- UUID
    session_id    TEXT NOT NULL REFERENCES chat_sessions(id),
    role          TEXT NOT NULL,              -- 'user' | 'assistant'
    content       TEXT NOT NULL,              -- 消息内容
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_messages_session ON chat_messages(session_id);

-- 引用表
CREATE TABLE citations (
    id            TEXT PRIMARY KEY,           -- UUID
    message_id    TEXT NOT NULL REFERENCES chat_messages(id),
    doc_id        TEXT NOT NULL REFERENCES documents(id),
    chunk_id      TEXT NOT NULL REFERENCES chunks(id),
    doc_name      TEXT NOT NULL,              -- 冗余存储，方便展示
    page_num      INTEGER,                    -- 页码
    chunk_index   INTEGER NOT NULL,           -- 块序号
    text_preview  TEXT NOT NULL,              -- chunk 前 200 字预览
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_citations_message ON citations(message_id);
```

#### 10.2 后续阶段扩展的表（Phase 2.5 ~ Phase 5 待实现）

> 注：tags 和 document_tags 表已在 Phase 2 实现并移入上一节。

```sql
-- 知识库分组表（Phase 2.5）
CREATE TABLE collections (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    doc_count     INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文档-分组关联（Phase 2.5，一对多，文档属于一个分组）
ALTER TABLE documents ADD COLUMN collection_id TEXT REFERENCES collections(id);

-- Chunk 质量评分表（Phase 4）
CREATE TABLE chunk_quality (
    chunk_id      TEXT PRIMARY KEY REFERENCES chunks(id),
    info_density  REAL DEFAULT 0.0,          -- 信息密度 0.0-1.0
    is_low_quality INTEGER DEFAULT 0,        -- 1 = 低质量（目录/版权/空白）
    reason        TEXT,                       -- 低质量原因
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PDF 提取的图片/表格（Phase 4）
CREATE TABLE chunk_images (
    id            TEXT PRIMARY KEY,
    chunk_id      TEXT NOT NULL REFERENCES chunks(id),
    image_path    TEXT NOT NULL,              -- 本地图片路径
    image_type    TEXT DEFAULT 'image',       -- 'image' | 'table'
    page_num      INTEGER,
    caption       TEXT,                       -- 图片说明
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_chunk_images_chunk ON chunk_images(chunk_id);

-- 知识图谱概念节点（Phase 5）
CREATE TABLE concepts (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    frequency     INTEGER DEFAULT 1,          -- 跨文档出现次数
    source_docs   TEXT,                       -- JSON: 来源文档 ID 列表
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 概念关联边（Phase 5）
CREATE TABLE concept_relations (
    id            TEXT PRIMARY KEY,
    source_id     TEXT NOT NULL REFERENCES concepts(id),
    target_id     TEXT NOT NULL REFERENCES concepts(id),
    relation_type TEXT DEFAULT 'co-occur',    -- 'co-occur' | 'sub-concept' | 'related'
    weight        REAL DEFAULT 1.0,           -- 关联强度
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 测验表（Phase 3）
CREATE TABLE quizzes (
    id            TEXT PRIMARY KEY,
    session_id    TEXT,
    topic         TEXT,                       -- 测验主题/范围
    total_count   INTEGER,
    correct_count INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 测验题目表（Phase 3）
CREATE TABLE quiz_questions (
    id            TEXT PRIMARY KEY,
    quiz_id       TEXT NOT NULL REFERENCES quizzes(id),
    question_type TEXT NOT NULL,              -- 'choice' | 'true_false' | 'fill' | 'short'
    question_text TEXT NOT NULL,
    options       TEXT,                       -- JSON: 选项列表
    correct_answer TEXT NOT NULL,
    explanation   TEXT,                       -- 答案解析
    source_chunk_id TEXT REFERENCES chunks(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 错题表（Phase 3）
CREATE TABLE wrong_answers (
    id            TEXT PRIMARY KEY,
    question_id   TEXT NOT NULL REFERENCES quiz_questions(id),
    user_answer   TEXT NOT NULL,
    review_count  INTEGER DEFAULT 0,          -- 复习次数
    last_reviewed TIMESTAMP,
    mastery_level INTEGER DEFAULT 0,          -- 0-5 掌握度
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识点表（Phase 3）
CREATE TABLE knowledge_points (
    id            TEXT PRIMARY KEY,
    doc_id        TEXT REFERENCES documents(id),
    name          TEXT NOT NULL,              -- 知识点名称
    description   TEXT,
    mastery_score REAL DEFAULT 0.0,           -- 掌握度 0.0-1.0
    next_review   TIMESTAMP,                  -- 下次复习时间（间隔重复）
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

### 十一、前端页面设计

#### 11.1 文档管理页

- 顶部：上传区域（拖拽 + 点击上传按钮）+ 「新建笔记」按钮（弹出文本输入框，保存为 note 类型文档）
- 列表：表格展示已上传文档（文件名、类型、分块数、上传时间、状态）
- 操作：每行可点击「删除」，确认后同步清理索引
- 状态指示：processing（解析中）、ready（就绪）、error（失败，悬浮显示错误原因）
- **【Phase 2 新增】标签管理**：每行文档显示标签列表（带 × 删除按钮），点击输入框可按 Enter 添加新标签
- **【Phase 2 新增】AI 摘要**：status=ready 的文档显示「AI 总结」按钮，点击后在紫色卡片中展示核心要点
- **【Phase 2.5 新增】分组筛选**：顶部增加 Collection 下拉选择器，可按分组过滤文档列表；上传时可选择所属分组

#### 11.2 问答页

- 左侧边栏：历史会话列表（可新建/删除会话）
- 中间：聊天区域，消息气泡展示，assistant 消息中的引用标记可点击展开原文片段
- 底部：输入框 + 发送按钮
- 引用展示：回答末尾显示 `[1] 文档A.pdf 第3页` 样式的引用，点击展开 chunk 原文
- **【Phase 2.5 新增】导出按钮**：每条 assistant 消息右下角增加「导出 MD」按钮
- **【Phase 4 新增】图表展示**：引用展开时若 chunk 有提取的图表，在原文旁展示图片
- **【Phase 4 新增】历史搜索**：左侧边栏顶部增加搜索框，支持全文/语义搜索历史对话

#### 11.3 RAG Debug 面板（问答页侧边抽屉）

- 触发：问答页右上角「Debug」按钮，点击展开右侧抽屉
- 展示内容：当前查询的 query、检索到的 top-k chunks（含分数）、完整 prompt、token 消耗、各阶段耗时
- 用途：开发调试 + 面试演示时展示 RAG 内部流程

#### 11.4 学习看板页（Phase 3 新增）

- 顶部卡片：总文档数、总 chunk 数、总提问数、连续学习天数
- 标签统计：各 tag 下的文档数和问答频率柱状图
- 薄弱知识点：掌握度最低的 10 个知识点列表（红色标记）
- 学习趋势：最近 30 天的每日提问数折线图

#### 11.5 测验页（Phase 3 新增）

- 出题配置：选择文档/tag 范围 + 题目数量 → 生成测验
- 答题界面：逐题展示（选择题单选 / 判断题），底部进度条
- 结果反馈：正确率 + 每题答案解析，错题高亮标记
- 错题本：单独 Tab 展示所有错题，支持重练和 Anki 导出

#### 11.6 知识图谱页（Phase 5 新增）

- 主区域：D3.js 力导向图，概念为节点（大小 = 出现频次），关联为边（粗细 = 权重）
- 交互：节点可拖拽、缩放，点击节点弹出关联文档列表和跳转链接
- 筛选：顶部 min_weight 滑块过滤弱关联，tag 下拉按标签过滤节点
- 推荐：问答页侧边栏新增"你可能还想了解"推荐卡片（基于知识图谱关联）

---

### 十二、技术栈

| 层级 | 技术 | 说明 |
|-----|------|------|
| 桌面壳 | **Tauri 2.x** | Rust 桥接层，包体积小（~10MB） |
| 前端 | **React 18 + TypeScript** | 组件化开发 |
| 样式 | **Tailwind CSS** | 快速开发 |
| 状态管理 | **Zustand** | 轻量，适合中小项目 |
| 后端框架 | **FastAPI** | Python，支持 SSE 流式响应 |
| 文档解析 | **PyMuPDF** (fitz) | PDF 文字提取，轻量无外部依赖 |
| 文本分块 | **自研分块器** | 不依赖 LangChain，逻辑简单可控 |
| 嵌入模型 | **bge-small-zh-v1.5** (sentence-transformers) | 中文效果好，本地推理 |
| 向量数据库 | **ChromaDB** | 本地文件存储，零运维 |
| 关系数据库 | **SQLite** | 本地元数据 + 聊天记录 |
| LLM | **Ollama (Qwen2.5-7B)** 默认 / **OpenAI API** 可选 | 本地优先，云端可选 |
| SSE | **FastAPI StreamingResponse** | 流式输出回答 |
| 图表可视化 | **D3.js** | 知识图谱力导向图（Phase 5） |
| 全文搜索 | **SQLite FTS5** | 对话历史全文检索（Phase 4） |

> MVP 阶段不引入 LangChain、LangGraph、LlamaIndex 等重框架。RAG 流程用原生 Python 实现，代码更透明、更可控，也更容易在面试中讲清楚原理。后续阶段按需引入。

---

### 十三、开发阶段规划

#### Phase 1 — MVP 核心 ✅ 已完成

**后端 RAG Pipeline：**
- ✅ FastAPI 项目骨架 + SQLite 数据库初始化（WAL 模式 + 外键约束）
- ✅ 文档上传接口 + 文件本地存储（~/.ai-study-assistant/data/documents/）
- ✅ PDF/TXT/MD 解析器（PyMuPDF + 原生文件读取 + 标题层级解析）
- ✅ 文本分块器（段落感知 + 句子边界兜底 + 64 token 重叠窗口）
- ✅ Embedding 生成 + ChromaDB 存储（cosine 空间，HNSW 索引，500 批量写入）
- ✅ 向量检索 + Prompt 构建 + LLM 调用（SSE 流式输出）
- ✅ 引用解析（[N] 正则提取 → chunk 映射）+ citation 写入
- ✅ 文档删除 + 索引同步清理（事务性三步删除：ChromaDB → SQLite → 本地文件）
- ✅ RAG Debug 信息记录（query、chunks、scores、timing、token usage）

**前端 + 联调：**
- ✅ React + Vite + TailwindCSS 项目搭建（Tauri 壳预留）
- ✅ 文档管理页（上传 + 列表 + 删除 + 笔记输入）
- ✅ 问答页（会话管理 + 聊天 + 引用展示 + SSE 流式接收）
- ✅ RAG Debug 面板（可展开侧边抽屉，显示 RAG 内部过程）
- ✅ 前后端联调 + API 代理（Vite proxy /api → localhost:8000）

**Phase 1 交付物：** 能上传 PDF/MD/TXT → 自动建索引 → 问答并获得带引用的回答 → Debug 面板查看 RAG 内部过程。

#### Phase 2 — 体验增强 ✅ 已完成

- ✅ 多轮对话上下文管理（最近 10 条消息传入 LLM，5 轮对话窗口）
- ✅ 手动输入笔记功能（POST /api/documents/note）
- ✅ 按主题/科目分类知识库（tags + document_tags 表，增删查接口）
- ✅ 查询改写 query rewrite（history >= 2 时触发，LLM 改写上下文依赖问题，失败回退原始问题）
- ✅ AI 摘要生成（POST /api/documents/{id}/summary，3-7 个核心要点）
- ✅ 前端标签管理 UI（标签展示 + × 删除 + Enter 添加）
- ✅ 前端摘要按钮（status=ready 时显示，紫色卡片展示结果）
- ✅ 前端会话侧边栏（历史会话列表 + 新建/切换）

**Phase 2 交付物：** 多轮对话可追问、文档可打标签分类管理、可一键生成文档摘要、query rewrite 提升检索质量。

#### Phase 2.5 — 工程实用（1 周，待开发）

- 知识库分组（多 Collection）：创建/管理知识库分组，上传文档时选择所属分组，问答时可按分组过滤检索
- 数据备份与导出：一键导出完整数据包（documents/ + chroma_db/ + app.db + config.json）为 zip，支持导入恢复
- Markdown 导出回答：将优质问答导出为 .md 文件（含引用来源），方便归档到 Obsidian/Notion

**Phase 2.5 交付物：** 可按项目/科目隔离知识库、数据可备份可恢复、好回答可导出归档。

#### Phase 3 — 学习系统（2 周，待开发）

- 基础测验生成（选择题 + 判断题，LLM 生成 JSON）
- 测验界面（答题 + 即时反馈 + 答案解析）
- 错题记录 + 重练
- 知识点掌握度追踪（基于正确率）
- 间隔重复复习（简化版艾宾浩斯）
- Anki 联动导出：将测验题 + 知识点导出为 Anki 兼容格式（.csv，含正面/反面/标签字段），可直接导入 Anki
- 学习进度看板：统计已上传资料数、知识覆盖率、各 tag 问答频率、薄弱知识点排名、学习时长趋势

**Phase 3 交付物：** 系统能自动出题 → 记录对错 → 追踪掌握度 → 导出到 Anki 做间隔重复 → 看板可视化学习进度。

#### Phase 4 — RAG 增强（1.5 周，待开发）

- BM25 关键词检索 + 向量检索混合（RRF 融合）
- Reranker 重排序（bge-reranker-v2-m3）
- LangGraph 重构：将 RAG 拆为 rewrite → retrieve → rerank → generate → evaluate 节点
- Self-Reflective RAG：evaluate 节点判断回答质量，不达标自动回退重试
- 引入 LangSmith 做链路追踪
- 对话历史搜索：SQLite FTS5 全文检索 + embedding 语义检索双通道搜索历史对话，快速找回之前的好问题
- Chunk 质量评分：上传后对每个 chunk 做信息密度评估（去重率、停用词比、实体密度），低质量 chunk（目录页、版权声明）自动标记并降权
- PDF 图表提取：PyMuPDF 提取 PDF 内嵌图片/表格，保存为 chunk 附加元数据，问答时可展示原始图表

**Phase 4 交付物：** 检索质量显著提升（混合检索 + 重排序 + 质量评分），可搜索历史对话，PDF 图表可追溯。

#### Phase 5 — 跨文档知识关联（1.5 周，待开发）

- 跨文档概念发现：对所有 chunks 做 NER + 关键词提取，自动发现跨文档的共同概念
- 知识图谱构建：以概念为节点、文档为来源、共现为边，构建轻量知识图谱（存 SQLite）
- 知识图谱可视化：前端用 D3.js 或 Recharts 绘制关系图，节点可点击跳转到相关文档/chunk
- 关联推荐：问答时自动推荐"你可能还想了解"的相关概念和文档

**Phase 5 交付物：** 系统能发现跨文档的知识关联，可视化展示概念网络，问答时提供关联推荐。

#### Phase 6 — Multi-Agent（2 周，待开发）

- Supervisor Agent：意图识别 + 任务路由
- Retriever Agent：专职检索（封装 Phase 4 的 RAG Graph）
- Tutor Agent：专职教学解释（基于检索结果做深入浅出的讲解）
- Examiner Agent：专职出题和评估（封装 Phase 3 的测验逻辑）
- Summarizer Agent：专职知识梳理
- Agent 间协作：学完自动出题、答错自动讲解

---

### 十四、失败场景处理

#### 14.1 文档处理阶段

| 失败场景 | 处理方式 |
|---------|---------|
| PDF 无法解析（加密/损坏） | 返回 422，前端提示"该 PDF 无法解析，请确认文件未加密且未损坏" |
| 扫描版 PDF 没有可提取文字 | 检测提取文字为空，返回 422，提示"该 PDF 为扫描版，暂不支持 OCR，请上传文字版 PDF 或其他格式" |
| 文档过大（>50MB） | 上传前校验文件大小，返回 413，提示"文件超过 50MB 限制" |
| 不支持的文件格式 | 返回 400，提示"仅支持 PDF、TXT、Markdown 格式" |
| 解析超时（>60s） | 设置超时，超时后标记 status=error，error_message="解析超时" |

#### 14.2 Embedding 阶段

| 失败场景 | 处理方式 |
|---------|---------|
| 本地模型加载失败 | 记录错误日志，fallback 到 OpenAI API（需用户配置 API Key） |
| Embedding API 调用失败 | 指数退避重试 3 次，仍失败则标记文档 status=error |
| 文本为空（解析结果为空） | 跳过该文档，标记 status=error，error_message="文档内容为空" |

#### 14.3 检索与生成阶段

| 失败场景 | 处理方式 |
|---------|---------|
| 向量库损坏 | 启动时校验 collection 完整性，损坏则提示用户重建索引 |
| 检索结果全部低于阈值 | 返回"资料中没有找到足够依据，建议上传相关资料或换一种问法" |
| LLM API 调用失败 | 指数退避重试 3 次，仍失败则返回"生成失败，请检查模型服务是否正常运行" |
| LLM 回答未包含引用标记 | 后处理检测无引用，附加警告"本回答未能标注具体来源，请核实" |
| Ollama 未启动 | 启动时检测，提示"本地模型服务未启动，请先运行 Ollama" |

#### 14.4 数据一致性

| 失败场景 | 处理方式 |
|---------|---------|
| 删除文档后索引未清理 | 删除操作使用事务：先删 ChromaDB 向量 → 再删 SQLite 记录 → 最后删本地文件，任一步骤失败则回滚 |
| 上传中途失败（断电/崩溃） | 文档标记为 status=processing，下次启动时自动清理未完成的文档 |
| 磁盘空间不足 | 上传前检查剩余空间，不足时提示"磁盘空间不足" |

#### 14.5 备份与导出（Phase 2.5）

| 失败场景 | 处理方式 |
|---------|---------|
| 备份时磁盘空间不足 | 导出前估算 zip 大小，检查目标路径剩余空间 |
| 导入 zip 格式损坏 | 校验 zip 完整性，损坏则返回"备份文件格式损坏" |
| 导入版本不兼容 | 备份包内记录版本号，导入时检查兼容性 |

#### 14.6 测验与 Anki 导出（Phase 3）

| 失败场景 | 处理方式 |
|---------|---------|
| LLM 生成题目 JSON 格式错误 | 解析失败时重试一次，仍失败则提示"题目生成失败，请重试" |
| 无足够 chunk 生成题目 | 提示"当前资料内容不足以生成测验，请上传更多资料" |
| Anki 导出无数据 | 检查是否有可导出的测验/知识点，为空则提示"没有可导出的内容" |

#### 14.7 知识图谱（Phase 5）

| 失败场景 | 处理方式 |
|---------|---------|
| NER 提取结果过少 | chunk 内容太短或过于碎片化时跳过，不建节点 |
| 图谱规模过大导致前端卡顿 | 限制节点数（默认 top 100 高频概念），支持 min_weight 过滤 |
| 关联噪声过多 | 设置共现阈值（≥ 2 次共现才建边），weight < 0.3 的边不展示 |

---

### 十五、本地优先与隐私设计

#### 数据存储位置

```
~/.ai-study-assistant/
├── data/
│   ├── documents/        # 原始文件（PDF/TXT/MD）
│   ├── chroma_db/        # ChromaDB 向量索引
│   ├── app.db            # SQLite 数据库
│   ├── chunk_images/     # PDF 提取的图表（Phase 4）
│   └── exports/          # 导出文件临时目录（MD/Anki/备份）
├── models/
│   └── bge-small-zh-v1.5/  # 本地嵌入模型
├── config.json           # 用户配置
└── logs/                 # 运行日志
```

#### 隐私规则

- **原始文件保存在本地**：`~/.ai-study-assistant/data/documents/`，不上传到任何服务器。
- **向量索引保存在本地**：ChromaDB 持久化到 `~/.ai-study-assistant/data/chroma_db/`。
- **聊天记录保存在本地**：SQLite 文件 `app.db` 包含所有会话和消息。
- **模型选择权在用户**：默认使用本地 Ollama，用户可切换 OpenAI API。
- **云端 API 调用前明确告知**：首次配置 OpenAI API 时，弹出提示说明"你的问题和检索到的文档片段将被发送到 OpenAI 服务器"。
- **支持完全清除**：删除知识库 = 删除本地文件 + 删除向量 + 删除元数据，不留残余。

---

### 十六、项目结构（参考）

```
ai-study-assistant/
├── frontend/                  # React 前端（Tauri 壳预留）
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Documents.tsx  # 文档管理页（含标签管理 + AI 摘要）
│   │   │   └── Chat.tsx       # 问答页（含会话侧边栏 + 引用展示）
│   │   ├── components/
│   │   │   └── DebugPanel.tsx # RAG Debug 面板
│   │   ├── api/
│   │   │   └── index.ts       # API 客户端 + TypeScript 类型定义
│   │   └── App.tsx            # React Router + 侧边导航
│   ├── package.json
│   ├── vite.config.ts         # Vite 配置 + API 代理
│   └── src-tauri/             # Tauri Rust 层（预留）
│
├── backend/                   # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py            # FastAPI 入口 + lifespan 初始化
│   │   ├── config.py          # 配置管理（pydantic-settings）
│   │   ├── routers/
│   │   │   ├── documents.py   # 文档 + 标签 + 摘要 API
│   │   │   └── chat.py        # 问答 API（SSE 流式）
│   │   ├── services/
│   │   │   ├── parser.py      # 文档解析（PDF/TXT/MD）
│   │   │   ├── chunker.py     # 文本分块（段落感知 + 句子边界）
│   │   │   ├── embedder.py    # Embedding 生成（OpenAI / 本地 BGE）
│   │   │   ├── vectorstore.py # ChromaDB 封装
│   │   │   ├── retriever.py   # 向量检索 + 阈值过滤
│   │   │   ├── generator.py   # LLM 调用 + 流式输出 + query rewrite
│   │   │   └── rag.py         # RAG 流程编排（ingest + query + delete）
│   │   ├── models/
│   │   │   └── schemas.py     # Pydantic 数据模型
│   │   └── db/
│   │       └── database.py    # SQLite 初始化 + 连接管理
│   ├── requirements.txt
│   ├── .env                   # 环境变量配置
│   └── tests/
│
├── docs/                      # 项目文档
│   ├── PRD.md                 # 本文件（产品需求文档）
│   └── TECHNICAL_DESIGN.md    # 技术设计文档（架构 + 数据流 + 决策）
│
└── README.md
```

---

### 十七、面试话术参考

这个项目作为 AI 工程项目放进简历时，可以这样讲：

**项目一句话**：基于 RAG 的本地 AI 学习助手，支持上传学习资料后进行智能问答、自动出题、知识图谱构建，所有回答均可溯源到原始文档的具体段落。

**技术亮点可讲的点**：自研文本分块策略（段落感知 + 字数兜底 + 重叠窗口）、混合检索方案（向量 + BM25 + RRF 融合）、RAG 质量控制系统（相似度阈值过滤 + Chunk 质量评分 + 引用强制标注 + Debug 面板可观测）、多轮对话 Query Rewrite（分离检索改写与生成输入，改写失败自动降级）、跨文档知识图谱构建（NER + 共现分析 + D3 可视化）、Anki 联动导出（学习闭环从资料导入到间隔重复复习）、本地优先架构设计（ChromaDB + SQLite + Ollama 全链路本地化）、从单 Pipeline 到 LangGraph 再到 Multi-Agent 的渐进式架构演进。

**面试官可能追问的点**：分块策略为什么这么设计（对比固定长度切分的劣势）、如何处理检索结果不相关的情况（阈值过滤 + Chunk 质量评分 + 后续引入 reranker）、为什么不用 LangChain（MVP 阶段原生实现更透明可控，后续按需引入 LangGraph）、如何保证数据一致性（删除事务 + 启动时清理孤儿数据）、Query Rewrite 为什么和 Generation 分离（检索需要完整独立查询，生成需要回应用户原始意图）、多轮对话上下文窗口为什么选 10 条（token 预算平衡）、知识图谱如何构建（对 chunks 做 NER 提取实体，跨文档共现分析建边，阈值过滤噪声关联）、为什么做 Anki 导出而不是自建间隔重复（复用成熟生态，用户已有 Anki 工作流）。
