## AI Study Assistant — 技术设计文档

---

### 一、系统架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                    Tauri/React 桌面应用（前端）                    │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────┐  │
│  │  文档管理页   │  │   智能问答页  │  │   RAG Debug Panel     │  │
│  │              │  │              │  │                        │  │
│  │ · 拖拽上传   │  │ · 会话管理   │  │ · query / rewritten   │  │
│  │ · 标签管理   │  │ · 多轮对话   │  │ · top-k chunks+score  │  │
│  │ · AI 摘要    │  │ · 引用溯源   │  │ · token usage         │  │
│  │ · 分块预览   │  │ · SSE 流式   │  │ · 各阶段耗时           │  │
│  └──────────────┘  └──────────────┘  └────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / SSE (EventSource)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI 后端（Python）                         │
│                                                                   │
│  ┌─── Routers ──────────────────────────────────────────────┐    │
│  │  documents.py          chat.py                             │    │
│  │  · upload / note       · chat (SSE stream)                 │    │
│  │  · list / delete       · sessions / messages               │    │
│  │  · tags (CRUD)         · delete session                    │    │
│  │  · chunks                                                  │    │
│  │  · summary                                               │    │
│  └────────────────────────┬───────────────────────────────────┘    │
│                           │                                        │
│  ┌─── Services ───────────▼───────────────────────────────────┐    │
│  │                                                            │    │
│  │  rag.py  ← 核心编排层                                       │    │
│  │  ┌──────────────────────────────────────────────────────┐  │    │
│  │  │ ingest: parse → chunk → embed → store (ChromaDB)    │  │    │
│  │  │ query:  rewrite → embed → retrieve → generate       │  │    │
│  │  │ delete: chroma → sqlite → file                      │  │    │
│  │  └──────────────────────────────────────────────────────┘  │    │
│  │                                                            │    │
│  │  parser.py    → PDF (PyMuPDF) / TXT / MD 解析              │    │
│  │  chunker.py   → 段落感知分块 + 句子边界兜底                  │    │
│  │  embedder.py  → OpenAI API / 本地 sentence-transformers     │    │
│  │  vectorstore.py → ChromaDB 封装 (cosine similarity)         │    │
│  │  retriever.py → Top-K 向量检索 + 相似度阈值过滤              │    │
│  │  generator.py → LLM 调用 + 引用提取 + Query Rewrite         │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─── Storage ────────────────────────────────────────────────┐    │
│  │  SQLite (app.db)       ChromaDB          本地文件系统       │    │
│  │  · documents           · 向量索引         · 原始文档        │    │
│  │  · chunks              · cosine 搜索      · ~/.ai-study-   │    │
│  │  · chat_sessions                          assistant/data/  │    │
│  │  · chat_messages                         documents/        │    │
│  │  · citations                                               │    │
│  │  · tags + document_tags                                    │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

### 二、核心数据流

#### 2.1 文档上传流程（Ingest Pipeline）

```
用户上传文件 (POST /api/documents/upload)
    │
    ▼
[router] documents.upload_document()
    │  1. 校验文件扩展名 (.pdf/.txt/.md)
    │  2. 校验文件大小 (≤50MB)
    │  3. 保存原始文件到 ~/.ai-study-assistant/data/documents/{uuid}/
    │
    ▼  (run_in_executor: 在线程池中运行，不阻塞事件循环)
[service] rag.ingest_document()
    │
    ├── Step 1: 记录文档元数据到 SQLite (status='processing')
    │
    ├── Step 2: 解析文档
    │   └── parser.parse(file_path, file_type)
    │       ├── PDF  → PyMuPDF 逐页提取文字，返回 ParsedSegment[]
    │       ├── TXT  → 直接读取全文，返回 1 个 ParsedSegment
    │       └── MD   → 按 # 标题拆分章节，每段保留 heading 元数据
    │
    ├── Step 3: 文本分块
    │   └── chunker.chunk_segments(segments)
    │       ├── 按 \n\n 段落切分
    │       ├── 累积段落直到达到 chunk_size (512 tokens)
    │       ├── 超长段落按中英文句子边界二次切分
    │       ├── 相邻块重叠 chunk_overlap (64 tokens)
    │       └── 每块携带 doc_id, chunk_index, page_num, heading
    │
    ├── Step 4: 生成 Embedding 向量
    │   └── embedder.embed(chunk_texts)
    │       ├── OpenAI: POST /v1/embeddings (text-embedding-3-small)
    │       └── Local:  sentence-transformers (bge-small-zh-v1.5)
    │
    ├── Step 5: 存入 ChromaDB
    │   └── vectorstore.add_chunks(ids, embeddings, texts, metadatas)
    │       └── 批量插入，每批 500 条
    │
    └── Step 6: 更新 SQLite (status='ready', chunk_count=N)
        └── 失败时: status='error', error_message='...'
```

#### 2.2 问答流程（Query Pipeline）

```
用户发送消息 (POST /api/chat, SSE)
    │
    ▼
[router] chat.chat()
    │  1. 创建/获取 session
    │  2. 从 SQLite 获取历史消息 → history[]
    │  3. 保存用户消息到 chat_messages
    │
    ▼
[service] rag.query(question, history)
    │
    ├── Step 0: Query Rewrite（仅当 history 存在时）
    │   └── generator.rewrite_query(question, history)
    │       ├── 构建改写 prompt：对话历史 + 用户问题
    │       ├── 调用 LLM 生成独立完整的查询
    │       └── 示例: "那第二章呢？" → "第二章中关于RAG的核心流程是什么？"
    │
    ├── Step 1: 向量检索
    │   └── retriever.retrieve(rewritten_query)
    │       ├── embedder.embed_query(query) → 查询向量
    │       ├── vectorstore.search(embedding, top_k=5)
    │       │   └── ChromaDB cosine similarity search
    │       └── 过滤: score < 0.3 的 chunk 丢弃
    │
    ├── Step 2: LLM 生成
    │   └── generator.generate(query, chunks, history)
    │       ├── 构建 system prompt:
    │       │   ├── 规则：只能基于参考资料回答
    │       │   ├── 规则：每个陈述标注 [N] 引用
    │       │   ├── 规则：信息不足时明确告知
    │       │   └── 如有 history: 附加"参考对话上下文"规则
    │       ├── 拼接 context: [1] 文档A p.3\n chunk_text \n---\n [2] ...
    │       ├── 构建 messages[]:
    │       │   ├── system: prompt + context
    │       │   ├── history[-10:]: 最近 5 轮对话
    │       │   └── user: 当前问题
    │       └── 调用 LLM → 返回 answer + citations
    │
    └── Step 3: 后处理
        ├── 解析 answer 中的 [N] 标记 → CitationMark[]
        ├── 映射到 chunks[N-1] → 提取 doc_name, page_num, chunk_id
        ├── 构建 DebugInfo (query, rewritten_query, scores, tokens, timing)
        └── 返回 (GenerationResult, DebugInfo)
    │
    ▼
[router] SSE event stream
    │  event: session    → { session_id }
    │  event: token      → { text }        (流式文本)
    │  event: citations  → [{ doc_name, page, chunk_id, preview }]
    │  event: debug      → { query, scores, tokens, timing }
    │  event: done       → { message_id, citations_count }
    │
    ▼
保存 assistant 消息 + citations 到 SQLite
```

#### 2.3 多轮对话上下文管理

```
第 1 轮: 用户 → "什么是RAG？"
    │  history = []  (空)
    │  → 不做 query rewrite
    │  → system prompt 不包含 HISTORY_NOTE
    │  → messages = [system, user]

第 2 轮: 用户 → "能详细解释向量检索吗？"
    │  history = [
    │    {role: "user", content: "什么是RAG？"},
    │    {role: "assistant", content: "RAG是检索增强生成..."},
    │  ]
    │  → 触发 query rewrite:
    │    "能详细解释向量检索吗？" → "RAG系统中的向量检索是如何工作的？"
    │  → system prompt 附加 HISTORY_NOTE
    │  → messages = [system, user(轮1), assistant(轮1), user(轮2)]
    │
    ▼
第 N 轮: 取最近 10 条消息 (5 轮) 作为上下文窗口
    防止 token 超限的同时保留足够上下文
```

#### 2.4 引用溯源机制

```
LLM 输出: "RAG的核心思想是在生成前检索相关文档[1]。向量检索使用余弦相似度[2]。"
    │
    ▼
正则提取: re.findall(r'\[(\d+)\]', text) → [1, 2]
    │
    ▼
映射: [1] → chunks[0] (第1个检索结果)
      [2] → chunks[1] (第2个检索结果)
    │
    ▼
CitationMark:
  · ref_index: 1
  · chunk_id: "uuid-xxx"
  · doc_name: "RAG技术文档.pdf"
  · page_num: 3
  · chunk_index: 7
  · text_preview: "RAG的核心思想是..." (前200字)
    │
    ▼
写入 citations 表 → 前端展示为可点击标记 → 点击展开原文片段
```

---

### 三、关键设计决策

#### 3.1 为什么 MVP 不用 LangChain/LangGraph？

**决策**：Phase 1-3 用原生 Python 实现 RAG Pipeline，Phase 4 再引入 LangGraph。

**原因**：
- 代码更透明可控，每一行逻辑都清晰可见
- 面试中能讲清楚每个环节的原理和实现
- 避免对框架的"黑盒依赖"，理解底层后再引入框架做增强
- LangGraph 的价值在复杂流程（条件分支、循环、多 Agent）中体现，MVP 不需要

**演进路线**：
```
Phase 1: parse → chunk → embed → retrieve → generate (线性 Pipeline)
Phase 4: LangGraph StateGraph
         ├── rewrite_query (条件: 有 history 时触发)
         ├── retrieve
         ├── rerank (Phase 4 新增)
         ├── generate
         └── evaluate → (条件边: 质量不达标 → rewrite_query)
```

#### 3.2 分块策略的设计思路

**目标**：保持语义完整性，同时在 token 限制和检索精度间取得平衡。

**策略分层**：
```
Level 1: 按段落切分 (\n\n)
  → 段落是自然语义单元，同一段落内的句子高度相关

Level 2: 累积段落到 chunk_size (512 tokens)
  → 512 tokens ≈ 750 中文字符，足够包含一个完整概念

Level 3: 超长段落按句子边界切分
  → 中英文句号/问号/感叹号作为句子结束标记
  → 避免单个句子被截断导致语义丢失

Level 4: 相邻块重叠 (64 tokens)
  → 确保跨块的概念不会完全丢失
  → 重叠部分作为"桥接"帮助检索命中
```

**对比方案**：
| 方案 | 优点 | 缺点 |
|------|------|------|
| 固定长度切分 (500字) | 简单 | 经常截断句子 |
| 递归字符切分 (LangChain) | 通用 | 不理解文档结构 |
| **段落感知 + 句子兜底** | **保持语义完整** | **实现稍复杂** |

#### 3.3 Embedding 模型选择

**OpenAI text-embedding-3-small**（默认）：
- 维度: 1536，效果好
- 需要 API Key，按 token 计费
- 适合快速验证和日常使用

**BGE-small-zh-v1.5**（本地备选）：
- 维度: 512，专为中文优化
- 完全本地，无 API 调用
- 需要安装 sentence-transformers，首次下载模型约 100MB

**切换方式**：修改 `.env` 中的 `ASA_EMBEDDING_PROVIDER` 即可，代码层面无需改动。

#### 3.4 相似度阈值过滤

**设计**：`score < 0.3` 的 chunk 直接丢弃，不送入 LLM。

**原因**：
- 低相似度 chunk 会引入噪声，降低回答质量
- 浪费 token 预算
- 如果所有 chunk 都低于阈值，说明资料中确实没有相关信息

**阈值选择依据**：
- Cosine similarity 0.3 ≈ 弱相关
- 实测中 0.3 以下的内容基本与查询无关
- 0.5 以上为中等相关，0.7 以上为强相关

#### 3.5 查询改写的触发条件

**设计**：仅在 `len(history) >= 2` 时触发 query rewrite。

**原因**：
- 第一轮对话没有上下文，不需要改写
- 改写需要额外一次 LLM 调用（增加延迟和成本）
- 短查询（如"那第二章呢？"）在有上下文时改写收益最大

**改写示例**：
```
对话历史:
  用户: "RAG系统中，文本分块有什么策略？"
  助手: "常见的分块策略有固定长度、递归字符、语义分块..."

用户新问题: "第二种呢？"
  ↓ rewrite
改写后: "RAG系统中递归字符分块策略的详细原理是什么？"
```

---

### 四、数据库设计思路

#### 4.1 表关系

```
documents (1) ──── (N) chunks
    │                    │
    │                    └── ChromaDB 中的向量通过 chunk_id 关联
    │
    └── (N:M) tags ──→ document_tags (关联表)

chat_sessions (1) ──── (N) chat_messages
                             │
                             └── (N) citations ──→ chunks (通过 chunk_id)
```

#### 4.2 为什么用 SQLite + ChromaDB 而不是纯向量库？

**SQLite 负责**：
- 结构化元数据（文件名、大小、状态、标签）
- 关系查询（某文档的所有分块、某消息的所有引用）
- 事务一致性（删除文档时级联清理）

**ChromaDB 负责**：
- 高维向量的 ANN (Approximate Nearest Neighbor) 搜索
- 使用 HNSW 索引，查询效率 O(log n)

**混合存储的优势**：
- 各取所长：结构化查询走 SQL，相似度搜索走向量库
- 数据一致性通过事务保证：先删向量 → 再删元数据 → 最后删文件
- 便于 Debug：可以直接查 SQLite 看分块内容和引用关系

#### 4.3 citations 表的设计考虑

```sql
CREATE TABLE citations (
    id          TEXT PRIMARY KEY,
    message_id  TEXT NOT NULL,   -- 关联到哪条消息
    doc_id      TEXT NOT NULL,   -- 来源文档
    chunk_id    TEXT NOT NULL,   -- 具体分块
    doc_name    TEXT NOT NULL,   -- 冗余: 避免 JOIN 查询
    page_num    INTEGER,         -- 冗余: 避免 JOIN 查询
    chunk_index INTEGER NOT NULL,
    text_preview TEXT NOT NULL,  -- 前200字预览
);
```

**冗余字段的设计理由**：
- `doc_name` 和 `page_num` 在 documents/chunks 表中也有
- 但前端展示引用时只需要这些信息，冗余存储避免了每次 JOIN 查询
- 文档删除时通过 `message_id` 级联清理，不会有孤立数据

---

### 五、前端架构思路

#### 5.1 技术选型

| 技术 | 选择理由 |
|------|---------|
| React + TypeScript | 类型安全，组件化开发，生态成熟 |
| Vite | 比 CRA 快 10x 的 HMR，适合中小项目 |
| TailwindCSS | 原子化 CSS，不用写 CSS 文件 |
| Zustand | 比 Redux 简单，适合中小状态管理 |
| React Router | 两个页面（文档管理 / 问答），路由简单 |

#### 5.2 SSE 流式响应的处理

```typescript
// 前端通过 fetch + ReadableStream 处理 SSE
const reader = res.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  // 解析 SSE 格式:
  // event: token
  // data: {"text": "..."}
  //
  // event: citations
  // data: [{...}]

  switch (currentEvent) {
    case 'session':  → 更新 sessionId
    case 'token':    → 追加到 streamingText（实时显示）
    case 'citations': → 保存引用列表
    case 'debug':    → 更新 Debug Panel
    case 'done':     → 流结束
  }
}
```

**为什么不用 EventSource？**
- EventSource 只支持 GET 请求
- 我们需要 POST 发送 JSON body（message + session_id）
- 所以用 fetch + ReadableStream 手动解析 SSE

#### 5.3 引用展示的交互设计

```
回答文本: "RAG的核心思想是检索增强生成[1]。向量检索使用余弦相似度[2]。"

引用标记: [1] RAG技术文档.pdf p.3    [2] RAG技术文档.pdf p.7
              ↓ 点击展开
         ┌─────────────────────────────┐
         │ 文档: RAG技术文档.pdf       │
         │ 页码: 第3页 · 块 #7         │
         │ ───────────────────────     │
         │ RAG（Retrieval-Augmented    │
         │ Generation，检索增强生成）是 │
         │ 一种将信息检索与大语言模型... │
         └─────────────────────────────┘
```

---

### 六、错误处理策略

#### 6.1 分层错误处理

```
[Router 层] → HTTP 状态码
  400: 不支持的格式
  404: 文档/会话不存在
  413: 文件过大
  422: 解析失败（扫描版PDF等）
  500: 内部错误

[Service 层] → 业务逻辑错误
  解析失败: ParseResult.error = "该PDF为扫描版..."
  Embedding 失败: 重试 3 次 → 标记 status='error'
  LLM 失败: 返回友好错误消息

[基础设施层] → 运行时错误
  SQLite 连接失败: 启动时检查
  ChromaDB 损坏: health_check() 检测
  磁盘空间不足: 上传前检查
```

#### 6.2 删除文档的事务性保证

```python
def delete_document(doc_id):
    try:
        # Step 1: 先删向量（最不可逆）
        chunks_deleted = vectorstore.delete_by_doc_id(doc_id)

        # Step 2: 删 SQLite 元数据
        DELETE FROM citations WHERE ...
        DELETE FROM chunks WHERE doc_id = ?
        DELETE FROM documents WHERE id = ?

        # Step 3: 删本地文件（最安全）
        os.remove(file_path)

        conn.commit()  # 事务提交
    except:
        conn.rollback()  # 任何步骤失败，回滚 SQLite
```

---

### 七、面试要点

#### 7.1 可以讲的技术亮点

1. **自研分块策略**：段落感知 + 句子兜底 + 重叠窗口，对比固定长度切分的优劣
2. **Query Rewrite**：多轮对话中改写模糊查询为独立完整查询
3. **引用溯源**：LLM 输出 [N] 标记 → 正则提取 → 映射到具体 chunk → 前端可交互
4. **相似度阈值**：低于 0.3 的 chunk 不送入 LLM，全部低于时返回"资料不足"
5. **事务性删除**：向量 → 元数据 → 文件，三步事务保证数据一致性
6. **本地优先架构**：SQLite + ChromaDB + Ollama，全链路本地化
7. **渐进式架构演进**：原生 Python → LangGraph → Multi-Agent

#### 7.2 可能的追问

**Q: 为什么相似度阈值选 0.3？**
A: Cosine similarity 0.3 以下的内容实测基本与查询无关。阈值太低会引入噪声，太高会漏掉相关内容。可以根据实际效果调整，也可以做成可配置参数。

**Q: 分块大小为什么选 512 tokens？**
A: 512 tokens ≈ 750 中文字，足够包含一个完整概念。太大则检索精度下降（一个 chunk 包含太多主题），太小则上下文丢失。这是 RAG 领域的常用经验值。

**Q: 如何保证 LLM 不会编造答案？**
A: 三道防线——① system prompt 强制约束只能基于资料回答；② 相似度阈值过滤，资料不足时直接拒绝；③ 后处理检测引用标记，无引用时附加警告。

**Q: 多轮对话的上下文窗口为什么是 10 条？**
A: 5 轮对话（10 条消息）提供了足够的上下文理解用户意图，同时控制在 ~2000 tokens 以内，不会挤占 RAG context 的 token 预算。可以根据实际对话长度动态调整。

**Q: Query Rewrite 增加了延迟，值吗？**
A: 只在有对话历史时触发。对于简短的追问（"那第二章呢？"），改写后检索质量提升显著。额外增加的 ~500ms 延迟换来了更准确的检索结果，是可接受的 trade-off。
