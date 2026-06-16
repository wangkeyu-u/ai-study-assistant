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
      llm_provider: 'openai',
      llm_model: 'gpt-4o-mini',
      embedding_provider: 'openai',
      embedding_model: 'text-embedding-3-small',
    });
  }),

  http.get('/api/settings/models', () => {
    return HttpResponse.json({
      providers: [
        {
          id: 'openai',
          label: 'OpenAI',
          base_url: null,
          api_key_env: 'OPENAI_API_KEY',
          docs_url: 'https://platform.openai.com/docs/models',
          openai_compatible: true,
          models: [{ id: 'gpt-4o-mini', label: 'GPT-4o mini', notes: 'test' }],
        },
      ],
      current: {
        llm_provider: 'openai',
        llm_model: 'gpt-4o-mini',
        llm_base_url: null,
      },
    });
  }),
];
