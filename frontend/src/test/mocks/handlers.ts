import { http, HttpResponse } from 'msw';

export const handlers = [
  // Health check
  http.get('/api/health', () => {
    return HttpResponse.json({
      status: 'ok',
      vector_store_healthy: true,
      vector_count: 0,
      embedding_provider: 'openai',
      llm_provider: 'openai',
      llm_model: 'gpt-4o-mini',
    });
  }),

  // List documents
  http.get('/api/documents', () => {
    return HttpResponse.json({ documents: [] });
  }),

  // List collections
  http.get('/api/collections', () => {
    return HttpResponse.json([]);
  }),

  // List chat sessions
  http.get('/api/chat/sessions', () => {
    return HttpResponse.json([]);
  }),

  // Create collection
  http.post('/api/collections', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 'test-collection-id',
      name: body.name,
      description: body.description || null,
      doc_count: 0,
      created_at: new Date().toISOString(),
    });
  }),

  // Quiz dashboard
  http.get('/api/quiz/dashboard', () => {
    return HttpResponse.json({
      total_documents: 0,
      total_chunks: 0,
      total_questions_asked: 0,
      total_quizzes: 0,
      tag_stats: [],
      weak_points: [],
      recent_activity: [],
    });
  }),

  // API key status
  http.get('/api/settings/api-key', () => {
    return HttpResponse.json({
      has_key: true,
      key_preview: 'sk-****test',
    });
  }),
];
