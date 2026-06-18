export const DEMO_DOCUMENT_TITLE = 'RAG Interview Demo';
export const DEMO_DOCUMENT_FILENAME = `${DEMO_DOCUMENT_TITLE}.txt`;

export const DEMO_DOCUMENT_CONTENT = `# Production RAG System Design

## Retrieval pipeline

The AI Study Assistant combines dense vector retrieval from ChromaDB with SQLite FTS5 keyword retrieval. Results from both channels are merged with Reciprocal Rank Fusion (RRF). This hybrid design improves recall for semantic questions while preserving exact matches for model names, metrics, and technical terms.

Compound questions are decomposed into at most three focused subqueries. Each subquery is retrieved independently, then all results are fused and deduplicated. A confidence gate rejects weak vector-only matches instead of sending unreliable evidence to the language model.

## Hallucination control

Answers must be grounded in retrieved chunks and use numbered citations such as [1] and [2]. A sentence-level citation validator checks factual claims after generation. Answers with missing citations or invalid citation indexes are replaced with a safe refusal. When retrieval finds no sufficiently relevant evidence, the system explicitly says that the available material is insufficient.

## Evaluation and observability

The retrieval benchmark tracks MRR, Hit@1, Hit@3, no-answer accuracy, hard-negative accuracy, and p95 latency. The current isolated hybrid baseline reports MRR 1.000, Hit@1 1.000, Hit@3 1.000, no-answer accuracy 1.000, and HardNeg@1 1.000 on the versioned evaluation corpus.

For every query, the Debug Panel exposes the rewritten query, decomposition subqueries, retrieval mode, vector and lexical scores, selected chunks, confidence decisions, token usage, and retrieval and generation latency. This makes failures inspectable instead of treating the RAG pipeline as a black box.

## Product workflow

Users can upload PDF, TXT, and Markdown files, organize them into collections, ask cited questions, generate quizzes, review mistakes, export Anki cards, and explore an automatically extracted knowledge graph. All documents, metadata, vectors, and chat history are stored locally by default.
`;

export const DEMO_QUESTIONS = [
  {
    kind: 'grounded',
    questionKey: 'documents.demoQuestionText1',
  },
  {
    kind: 'multiHop',
    questionKey: 'documents.demoQuestionText2',
  },
  {
    kind: 'refusal',
    questionKey: 'documents.demoQuestionText3',
  },
] as const;
