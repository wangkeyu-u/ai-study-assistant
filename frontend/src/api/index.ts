import i18n from '../i18n';

const BASE_URL = '/api';

export function getApiErrorMessage(key: string): string {
  return i18n.t(key);
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/** Fetch a URL and parse JSON, throwing on HTTP errors. */
async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Types ─────────────────────────────────────────────────

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: 'processing' | 'ready' | 'error';
  error_message?: string | null;
  tags: string[];
  collection_id?: string | null;
  collection_name?: string | null;
  created_at: string;
}

export interface Tag {
  id: string;
  name: string;
  doc_count: number;
}

export interface Collection {
  id: string;
  name: string;
  description?: string | null;
  doc_count: number;
  created_at: string;
}

export interface Summary {
  doc_id: string;
  filename: string;
  summary: string;
}

export interface ChunkInfo {
  chunk_id: string;
  text_preview: string;
  page_num?: number | null;
  heading?: string | null;
  chunk_index: number;
}

export interface ChatSession {
  id: string;
  title: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  doc_name: string;
  page_num?: number | null;
  chunk_id: string;
  chunk_index: number;
  text_preview: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface DebugInfo {
  query: string;
  rewritten_query?: string | null;
  retrieval_queries?: string[];
  embedding_model: string;
  retrieval_mode?: string;
  confidence_rejected?: boolean;
  confidence_score?: number | null;
  rejection_reason?: string | null;
  top_k_chunks: {
    chunk_id: string;
    text_preview: string;
    similarity_score: number;
    doc_name: string;
    page_num?: number | null;
    vector_score?: number | null;
    lexical_score?: number | null;
    rerank_score?: number | null;
    retrieval_sources?: string[];
  }[];
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  retrieval_time_ms: number;
  generation_time_ms: number;
}

export interface ChatStreamResult {
  content: string;
  citations: Citation[];
  sessionId?: string;
  messageId?: string;
  agentName?: string;
  debug?: DebugInfo;
}

export interface ChatStreamHandlers {
  onToken?: (text: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onDebug?: (debug: DebugInfo) => void;
  onSessionId?: (id: string) => void;
}

// ── Document API ─────────────────────────────────────────

export async function uploadDocument(file: File, collectionId?: string): Promise<Document> {
  const formData = new FormData();
  formData.append('file', file);
  let url = `${BASE_URL}/documents/upload`;
  if (collectionId) url += `?collection_id=${encodeURIComponent(collectionId)}`;
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.uploadFailed'));
  }
  return res.json();
}

export async function createNote(
  title: string,
  content: string,
  collectionId?: string
): Promise<Document> {
  const params = new URLSearchParams({ title, content });
  if (collectionId) params.set('collection_id', collectionId);
  const res = await fetch(`${BASE_URL}/documents/note?${params}`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.createFailed'));
  }
  return res.json();
}

export async function listDocuments(): Promise<Document[]> {
  const data = await fetchJson<{ documents: Document[] }>(`${BASE_URL}/documents`);
  return data.documents;
}

export async function getChunks(docId: string): Promise<ChunkInfo[]> {
  return fetchJson<ChunkInfo[]>(`${BASE_URL}/documents/${docId}/chunks`);
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(getApiErrorMessage('api.deleteFailed'));
}

// ── Tag API ───────────────────────────────────────────────

export async function addTag(docId: string, tagName: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag_name: tagName }),
  });
  if (!res.ok) throw new Error(getApiErrorMessage('api.addTagFailed'));
}

export async function removeTag(docId: string, tagName: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/tags/${encodeURIComponent(tagName)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(getApiErrorMessage('api.removeTagFailed'));
}

export async function listAllTags(): Promise<{ id: string; name: string; doc_count: number }[]> {
  return fetchJson(`${BASE_URL}/documents/tags/all`);
}

// ── Collection API ────────────────────────────────────────

export async function listCollections(): Promise<Collection[]> {
  return fetchJson<Collection[]>(`${BASE_URL}/collections`);
}

export async function createCollection(name: string, description?: string): Promise<Collection> {
  const res = await fetch(`${BASE_URL}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.createCollectionFailed'));
  }
  return res.json();
}

export async function deleteCollection(collectionId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/collections/${collectionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(getApiErrorMessage('api.deleteCollectionFailed'));
}

export async function assignDocToCollection(
  docId: string,
  collectionId: string | null
): Promise<void> {
  const res = await fetch(`${BASE_URL}/collections/documents/${docId}/collection`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ collection_id: collectionId }),
  });
  if (!res.ok) throw new Error(getApiErrorMessage('api.assignCollectionFailed'));
}

// ── Summary API ───────────────────────────────────────────

export async function generateSummary(
  docId: string
): Promise<{ doc_id: string; filename: string; summary: string }> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/summary`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.summaryFailed'));
  }
  return res.json();
}

// ── Chat API ──────────────────────────────────────────────

export async function listSessions(): Promise<ChatSession[]> {
  return fetchJson<ChatSession[]>(`${BASE_URL}/chat/sessions`);
}

export async function getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  return fetchJson<ChatMessage[]>(`${BASE_URL}/chat/sessions/${sessionId}/messages`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/chat/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(getApiErrorMessage('api.deleteFailed'));
}

type SsePayload = Record<string, unknown> | unknown[];

async function consumeChatStream(
  response: Response,
  handlers: ChatStreamHandlers = {}
): Promise<ChatStreamResult> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  if (!response.body) throw new Error('No response body');

  const result: ChatStreamResult = { content: '', citations: [] };
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  const processEvent = (block: string) => {
    if (!block.trim()) return;

    let eventType = 'message';
    const dataLines: string[] = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) eventType = line.slice(6).trim();
      if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
    }
    if (dataLines.length === 0) return;

    let payload: SsePayload;
    try {
      payload = JSON.parse(dataLines.join('\n')) as SsePayload;
    } catch {
      throw new Error('服务端返回了无效的流式数据');
    }

    if (eventType === 'citations' && Array.isArray(payload)) {
      result.citations = payload as Citation[];
      handlers.onCitations?.(result.citations);
      return;
    }
    if (Array.isArray(payload)) return;

    if (eventType === 'session' && typeof payload.session_id === 'string') {
      result.sessionId = payload.session_id;
      handlers.onSessionId?.(payload.session_id);
    } else if (eventType === 'token' && typeof payload.text === 'string') {
      result.content += payload.text;
      handlers.onToken?.(payload.text);
    } else if (eventType === 'debug') {
      result.debug = payload as unknown as DebugInfo;
      handlers.onDebug?.(result.debug);
    } else if (eventType === 'error') {
      throw new Error(typeof payload.error === 'string' ? payload.error : '流式请求失败');
    } else if (eventType === 'done') {
      if (typeof payload.error === 'string') throw new Error(payload.error);
      if (typeof payload.message_id === 'string') result.messageId = payload.message_id;
      if (typeof payload.agent_name === 'string') result.agentName = payload.agent_name;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });

    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() ?? '';
    blocks.forEach(processEvent);

    if (done) break;
  }
  processEvent(buffer);
  return result;
}

export async function sendChatMessage(
  message: string,
  sessionId?: string,
  collectionId?: string | null,
  handlers?: ChatStreamHandlers
): Promise<ChatStreamResult> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message, collection_id: collectionId }),
  });
  return consumeChatStream(res, handlers);
}

// ── History Search ────────────────────────────────────────

export interface HistorySearchResult {
  message_id: string;
  session_id: string;
  session_title: string;
  role: string;
  content_preview: string;
  score: number;
  created_at: string;
}

export async function searchHistory(q: string, mode?: string): Promise<HistorySearchResult[]> {
  const params = new URLSearchParams({ q });
  if (mode) params.set('mode', mode);
  const res = await fetch(`${BASE_URL}/chat/search?${params}`);
  if (!res.ok) return [];
  return res.json();
}

// ── Backup API ────────────────────────────────────────────

export async function exportBackup(): Promise<void> {
  const res = await fetch(`${BASE_URL}/backup/export`, { method: 'POST' });
  if (!res.ok) throw new Error(getApiErrorMessage('api.exportBackupFailed'));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `ai-study-backup-${new Date().toISOString().slice(0, 10)}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function importBackup(
  file: File
): Promise<{ success: boolean; documents_restored: number }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/backup/import`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.importFailed'));
  }
  return res.json();
}

// ── Markdown Export ───────────────────────────────────────

export async function exportMessageAsMarkdown(messageId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/backup/export-md/${messageId}`, { method: 'POST' });
  if (!res.ok) throw new Error(getApiErrorMessage('api.exportFailed'));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `answer-${messageId.slice(0, 8)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── Quiz Types ────────────────────────────────────────────

export interface QuizQuestion {
  id: string;
  question_type: 'choice' | 'true_false';
  question_text: string;
  options?: string[] | null;
  correct_answer?: string | null;
  explanation?: string | null;
}

export interface Quiz {
  id: string;
  topic?: string | null;
  total_count: number;
  questions: QuizQuestion[];
  created_at: string;
}

export interface QuizResult {
  quiz_id: string;
  correct_count: number;
  total_count: number;
  results: {
    question_id: string;
    question_text: string;
    user_answer: string;
    correct_answer: string;
    is_correct: boolean;
    explanation?: string | null;
  }[];
}

export interface WrongAnswer {
  id: string;
  question_text: string;
  question_type: string;
  options?: string[] | null;
  correct_answer: string;
  explanation?: string | null;
  user_answer: string;
  review_count: number;
  mastery_level: number;
  created_at: string;
}

export interface DashboardData {
  total_documents: number;
  total_chunks: number;
  total_questions_asked: number;
  total_quizzes: number;
  total_correct_answers: number;
  wrong_answer_count: number;
  tag_stats: { tag: string; doc_count: number; question_count: number }[];
  weak_points: { concept: string; mastery_score: number }[];
  recent_activity: { date: string; questions_count: number; sessions: number }[];
}

// ── Quiz API ──────────────────────────────────────────────

export async function generateQuiz(params: {
  doc_ids?: string[];
  tag?: string;
  count?: number;
}): Promise<Quiz> {
  const res = await fetch(`${BASE_URL}/quiz/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '' }));
    throw new Error(err.detail || getApiErrorMessage('api.generateQuizFailed'));
  }
  return res.json();
}

export async function submitQuiz(
  quizId: string,
  answers: { question_id: string; user_answer: string }[]
): Promise<QuizResult> {
  const res = await fetch(`${BASE_URL}/quiz/${quizId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error(getApiErrorMessage('api.submitFailed'));
  return res.json();
}

export async function listWrongAnswers(): Promise<WrongAnswer[]> {
  return fetchJson<WrongAnswer[]>(`${BASE_URL}/quiz/wrong-answers`);
}

export async function reviewWrongAnswer(
  answerId: string,
  isCorrect: boolean
): Promise<{ mastery_level: number; removed: boolean }> {
  const res = await fetch(
    `${BASE_URL}/quiz/wrong-answers/${answerId}/review?is_correct=${isCorrect}`,
    {
      method: 'POST',
    }
  );
  if (!res.ok) throw new Error(getApiErrorMessage('api.reviewFailed'));
  return res.json();
}

export async function exportAnki(params?: { tag?: string; doc_id?: string }): Promise<void> {
  const query = new URLSearchParams();
  if (params?.tag) query.set('tag', params.tag);
  if (params?.doc_id) query.set('doc_id', params.doc_id);
  const qs = query.toString();
  const res = await fetch(`${BASE_URL}/quiz/anki/export${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error(getApiErrorMessage('api.exportFailed'));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'anki-export.txt';
  a.click();
  URL.revokeObjectURL(url);
}

export async function getDashboard(): Promise<DashboardData> {
  return fetchJson<DashboardData>(`${BASE_URL}/quiz/dashboard`);
}

// ── Knowledge Graph API ──────────────────────────────────

export interface GraphNode {
  id: string;
  name: string;
  category: string;
  description: string;
  doc_count: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation_type: string;
  strength: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RelatedConcept {
  name: string;
  category: string;
  description: string;
  relation_type: string;
  strength: number;
  direction: string;
}

export interface BuildResult {
  success: boolean;
  documents_processed: number;
  concepts_added: number;
  relations_added: number;
}

export const knowledgeGraphApi = {
  async build(docIds?: string[]): Promise<BuildResult> {
    const res = await fetch(`${BASE_URL}/knowledge-graph/build`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_ids: docIds }),
    });
    if (!res.ok) throw new Error(getApiErrorMessage('api.buildGraphFailed'));
    return res.json();
  },

  async getGraph(docIds?: string[]): Promise<GraphData> {
    const query = docIds ? `?doc_ids=${docIds.join(',')}` : '';
    const res = await fetch(`${BASE_URL}/knowledge-graph${query}`);
    if (!res.ok) throw new Error(getApiErrorMessage('api.getGraphFailed'));
    return res.json();
  },

  async getRelated(
    conceptName: string,
    topK: number = 5
  ): Promise<{ concept: string; related: RelatedConcept[] }> {
    const res = await fetch(
      `${BASE_URL}/knowledge-graph/related?q=${encodeURIComponent(conceptName)}&top_k=${topK}`
    );
    if (!res.ok) throw new Error(getApiErrorMessage('api.getRelatedFailed'));
    return res.json();
  },
};

// ── Multi-Agent API ────────────────────────────────────

export async function sendMultiAgentChat(
  message: string,
  sessionId?: string,
  collectionId?: string | null,
  handlers?: ChatStreamHandlers
): Promise<ChatStreamResult> {
  const res = await fetch(`${BASE_URL}/multi-agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId, collection_id: collectionId }),
  });
  return consumeChatStream(res, handlers);
}

// ── Health ─────────────────────────────────────────────────

export async function healthCheck(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`${BASE_URL}/health`);
}

// ── Settings API ──────────────────────────────────────────

export interface ApiKeyStatus {
  has_key: boolean;
  key_preview: string;
  llm_provider: string;
  llm_model: string;
  embedding_provider: string;
  embedding_model: string;
}

export interface ApiKeyUpdateResponse {
  success: boolean;
  message: string;
}

export async function getApiKeyStatus(): Promise<ApiKeyStatus> {
  const res = await fetch(`${BASE_URL}/settings/api-key`);
  if (!res.ok) throw new Error(getApiErrorMessage('api.getApiKeyStatusFailed'));
  return res.json();
}

export async function updateApiKey(apiKey: string): Promise<ApiKeyUpdateResponse> {
  const res = await fetch(`${BASE_URL}/settings/api-key`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) throw new Error(getApiErrorMessage('api.updateApiKeyFailed'));
  return res.json();
}
