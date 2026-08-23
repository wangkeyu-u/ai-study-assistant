# Interview Playbook

## 30 秒项目定位

AI Study Assistant 是一个本地优先的 RAG 学习工作台。它不是简单的 chat-with-PDF，而是把文档摄入、混合检索、查询规划、上下文优化、带引用生成、质量门控、学习测验和知识图谱串成一个可演示、可观测、可扩展的 AI 应用框架。

## 面试官应该看到什么

1. 打开 Dashboard，看 **RAG Capability Console**。
2. 打开 Documents，载入 Interview Demo。
3. 打开 Chat，问一个有依据问题，展开引用和 Debug Panel。
4. 问一个多跳问题，展示 retrieval queries、intent、context strategy。
5. 上传英文资料，用中文提问并切换中英文回答，展示跨语言检索。
6. 问一个资料外问题，展示 safe refusal、coverage gate、zero token LLM spend。

## 可以讲的架构亮点

### 1. Low-code AI 应用框架感

- 模型供应商可配置：OpenAI-compatible、DeepSeek、Gemini、Qwen、Moonshot、Mistral、Zhipu、xAI、OpenRouter、Ollama。
- RAG 参数可配置：chunk size、overlap、top-k、candidate top-k、MMR、coverage gate、reranker。
- 能力模块化：parser、chunker、embedder、retriever、query intelligence、context optimizer、generator、citation validator。

### 2. 检索不是只做向量搜索

- Dense vector retrieval 解决语义相似。
- SQLite FTS5 解决关键词、术语、缩写、精确匹配。
- Reciprocal Rank Fusion 合并多路检索结果。
- Query decomposition 把复合问题拆成多个子查询。
- 语料语言检测会按当前知识库范围采样；查询翻译后与原查询共同召回，再用 RRF 融合。
- 普通召回失败时才启用 HyDE，且假设文本不能作为最终证据通过 coverage gate。

### 3. 上下文不是直接 top-k 塞给模型

- 先召回更多候选。
- 用 intent-aware MMR 做去重和多样性选择。
- 多文档对比时强制保留每个文档的证据覆盖。
- 命中块会按预算补充相邻块，修复定义、表格说明或步骤跨 chunk 被截断的问题。
- coverage gate 在上下文不支持问题时提前拒答，减少幻觉和模型成本。

### 4. 生成不是黑盒

- Query intent 会影响回答结构：comparison、summary、process、definition、evidence-first、QA。
- 每个事实句必须带引用。
- Citation validator 会拒绝缺引用或越界引用的回答。
- Debug Panel 暴露 rewritten query、retrieval queries、scores、context strategy、token usage、latency。

## 推荐演示问题

### 有据回答

```text
这个系统通过哪些机制降低 RAG 回答中的幻觉风险？
```

讲法：看引用、source preview、Debug Panel 里的 retrieval sources。

### 多跳综合

```text
混合检索、多跳查询和质量评估是如何协同工作的？请结合指标说明。
```

讲法：看 retrieval queries、RRF、多跳融合、context strategy。

### 安全拒答

```text
资料是否说明量子计算会在 2028 年全面替代 GPU？
```

讲法：这是 RAG 项目的分水岭。好的系统应该知道资料不足，而不是编。

### 跨语言检索

```text
给英文资料后问：这个系统的 retrieval pipeline 包含哪些阶段？
```

讲法：先看 Debug Panel 中中文原查询和英文 retrieval query，再分别选择中文、英文回答。强调“检索语言”和“回答语言”是两个独立控制面。

## 被追问时怎么回答

**为什么不用单纯向量检索？**

向量检索适合语义召回，但对缩写、专业名词、数字、页面术语不稳定。所以我做了 vector + FTS5 + exact term，再用 RRF 融合。

**为什么需要 context optimizer？**

检索 top-k 是候选，不等于生成上下文。直接塞 top-k 容易重复、偏向单一文档、浪费 token。Context optimizer 负责把候选压缩成更适合回答的证据包。

**为什么 coverage gate 重要？**

它可以在“语义相似但实际无关”的情况下提前拒答，避免无关上下文诱导模型编答案，也节省 LLM 调用成本。

**这个项目和低代码有什么关系？**

低代码 AI 平台关注的是可配置、可组合、可观测、可治理。这个项目把 RAG 拆成多个可替换模块，并提供参数、调试、质量门控和演示脚本，已经接近一个小型 AI workflow runtime。

## 还可以继续升级的方向

- Workflow builder：把摄入、检索、重排、生成、评估做成可视化节点。
- Dataset studio：在 UI 中维护 golden questions 和 hard negatives。
- Evaluator agent：每次回答自动打 groundedness、citation coverage、answer completeness。
- Human feedback loop：用户对回答和引用打分，形成改进数据。
- Deployment profile：一键切换 local、interview、production 三套配置。
