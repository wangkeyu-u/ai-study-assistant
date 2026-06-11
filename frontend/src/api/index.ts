const BASE_URL = '/api';

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
  embedding_model: string;
  top_k_chunks: {
    chunk_id: string;
    text_preview: string;
    similarity_score: number;
    doc_name: string;
    page_num?: number | null;
  }[];
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  retrieval_time_ms: number;
  generation_time_ms: number;
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
    const err = await res.json().catch(() => ({ detail: '上传失败' }));
    throw new Error(err.detail || '上传失败');
  }
  return res.json();
}

export async function createNote(title: string, content: string): Promise<Document> {
  const res = await fetch(
    `${BASE_URL}/documents/note?title=${encodeURIComponent(title)}&content=${encodeURIComponent(content)}`,
    { method: 'POST' },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '创建失败' }));
    throw new Error(err.detail || '创建失败');
  }
  return res.json();
}

export async function listDocuments(): Promise<Document[]> {
  const res = await fetch(`${BASE_URL}/documents`);
  const data = await res.json();
  return data.documents;
}

export async function getChunks(docId: string): Promise<ChunkInfo[]> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/chunks`);
  return res.json();
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('删除失败');
}

// ── Tag API ───────────────────────────────────────────────

export async function addTag(docId: string, tagName: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/tags`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tag_name: tagName }),
  });
  if (!res.ok) throw new Error('添加标签失败');
}

export async function removeTag(docId: string, tagName: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/tags/${encodeURIComponent(tagName)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('删除标签失败');
}

export async function listAllTags(): Promise<{ id: string; name: string; doc_count: number }[]> {
  const res = await fetch(`${BASE_URL}/documents/tags/all`);
  return res.json();
}

// ── Collection API ────────────────────────────────────────

export async function listCollections(): Promise<Collection[]> {
  const res = await fetch(`${BASE_URL}/collections`);
  return res.json();
}

export async function createCollection(name: string, description?: string): Promise<Collection> {
  const res = await fetch(`${BASE_URL}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '创建分组失败' }));
    throw new Error(err.detail || '创建分组失败');
  }
  return res.json();
}

export async function deleteCollection(collectionId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/collections/${collectionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('删除分组失败');
}

export async function assignDocToCollection(docId: string, collectionId: string | null): Promise<void> {
  const res = await fetch(`${BASE_URL}/collections/documents/${docId}/collection`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ collection_id: collectionId }),
  });
  if (!res.ok) throw new Error('分配分组失败');
}

// ── Summary API ───────────────────────────────────────────

export async function generateSummary(docId: string): Promise<{ doc_id: string; filename: string; summary: string }> {
  const res = await fetch(`${BASE_URL}/documents/${docId}/summary`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '摘要生成失败' }));
    throw new Error(err.detail || '摘要生成失败');
  }
  return res.json();
}

// ── Chat API ──────────────────────────────────────────────

export async function listSessions(): Promise<ChatSession[]> {
  const res = await fetch(`${BASE_URL}/chat/sessions`);
  return res.json();
}

export async function getSessionMessages(sessionId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE_URL}/chat/sessions/${sessionId}/messages`);
  return res.json();
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE_URL}/chat/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function sendChatMessage(
  message: string,
  sessionId?: string,
  onToken?: (text: string) => void,
  onCitations?: (citations: Citation[]) => void,
  onDebug?: (debug: DebugInfo) => void,
  onSessionId?: (id: string) => void,
): Promise<void> {
  const res = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!res.ok) throw new Error('发送失败');
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        const eventType = line.slice(7).trim();
        continue;
      }
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        // Determine event type from the previous event line
        const eventLine = lines.find(l => l.startsWith('event: '));
        const eventType = eventLine ? eventLine.slice(7).trim() : '';

        // Parse SSE properly
        if (data.session_id) onSessionId?.(data.session_id);
        if (data.text !== undefined) onToken?.(data.text);
        if (Array.isArray(data)) onCitations?.(data);
        if (data.query) onDebug?.(data);
      }
    }
  }
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
  if (!res.ok) throw new Error('导出备份失败');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `ai-study-backup-${new Date().toISOString().slice(0, 10)}.zip`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function importBackup(file: File): Promise<{ success: boolean; documents_restored: number }> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${BASE_URL}/backup/import`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '导入失败' }));
    throw new Error(err.detail || '导入失败');
  }
  return res.json();
}

// ── Markdown Export ───────────────────────────────────────

export async function exportMessageAsMarkdown(messageId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/backup/export-md/${messageId}`, { method: 'POST' });
  if (!res.ok) throw new Error('导出失败');
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
    const err = await res.json().catch(() => ({ detail: '生成测验失败' }));
    throw new Error(err.detail || '生成测验失败');
  }
  return res.json();
}

export async function submitQuiz(quizId: string, answers: { question_id: string; user_answer: string }[]): Promise<QuizResult> {
  const res = await fetch(`${BASE_URL}/quiz/${quizId}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) throw new Error('提交失败');
  return res.json();
}

export async function listWrongAnswers(): Promise<WrongAnswer[]> {
  const res = await fetch(`${BASE_URL}/quiz/wrong-answers`);
  return res.json();
}

export async function reviewWrongAnswer(answerId: string, isCorrect: boolean): Promise<{ mastery_level: number; removed: boolean }> {
  const res = await fetch(`${BASE_URL}/quiz/wrong-answers/${answerId}/review?is_correct=${isCorrect}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('复习失败');
  return res.json();
}

export async function exportAnki(params?: { tag?: string; doc_id?: string }): Promise<void> {
  const query = new URLSearchParams();
  if (params?.tag) query.set('tag', params.tag);
  if (params?.doc_id) query.set('doc_id', params.doc_id);
  const qs = query.toString();
  const res = await fetch(`${BASE_URL}/quiz/anki/export${qs ? '?' + qs : ''}`);
  if (!res.ok) throw new Error('导出失败');
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'anki-export.txt';
  a.click();
  URL.revokeObjectURL(url);
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await fetch(`${BASE_URL}/quiz/dashboard`);
  return res.json();
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
    if (!res.ok) throw new Error('构建知识图谱失败');
    return res.json();
  },

  async getGraph(docIds?: string[]): Promise<GraphData> {
    const query = docIds ? `?doc_ids=${docIds.join(',')}` : '';
    const res = await fetch(`${BASE_URL}/knowledge-graph${query}`);
    if (!res.ok) throw new Error('获取知识图谱失败');
    return res.json();
  },

  async getRelated(conceptName: string, topK: number = 5): Promise<{ concept: string; related: RelatedConcept[] }> {
    const res = await fetch(`${BASE_URL}/knowledge-graph/related?q=${encodeURIComponent(conceptName)}&top_k=${topK}`);
    if (!res.ok) throw new Error('获取相关概念失败');
    return res.json();
  },
};

// ── Multi-Agent API ────────────────────────────────────

export interface MultiAgentResponse {
  content: string;
  agent_name: string;
  metadata: Record<string, unknown>;
}

export async function sendMultiAgentChat(
  message: string,
  sessionId?: string,
): Promise<MultiAgentResponse> {
  const res = await fetch(`${BASE_URL}/multi-agent/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error('Multi-Agent 请求失败');
  return res.json();
}

// ── Health ─────────────────────────────────────────────────

export async function healthCheck(): Promise<Record<string, unknown>> {
  const res = await fetch(`${BASE_URL}/health`);
  return res.json();
}
