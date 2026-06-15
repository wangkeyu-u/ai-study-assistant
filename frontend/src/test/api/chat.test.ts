import { afterEach, describe, expect, it, vi } from 'vitest';
import { sendChatMessage } from '../../api';

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    { status: 200, headers: { 'Content-Type': 'text/event-stream' } }
  );
}

describe('chat SSE client', () => {
  afterEach(() => vi.restoreAllMocks());

  it('handles events split across network chunks', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      streamResponse([
        'event: session\ndata: {"session_id":"session-1"}\n\nevent: to',
        'ken\ndata: {"text":"你"}\n\nevent: token\ndata: {"text":"好"}\n\n',
        'event: citations\ndata: []\n\nevent: done\ndata: {"message_id":"message-1"}\n\n',
      ])
    );
    const tokens: string[] = [];

    const result = await sendChatMessage('hello', undefined, null, {
      onToken: (token) => tokens.push(token),
    });

    expect(result).toMatchObject({
      content: '你好',
      citations: [],
      sessionId: 'session-1',
      messageId: 'message-1',
    });
    expect(tokens).toEqual(['你', '好']);
  });

  it('rejects backend error events', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      streamResponse(['event: error\ndata: {"error":"model unavailable"}\n\n'])
    );

    await expect(sendChatMessage('hello')).rejects.toThrow('model unavailable');
  });
});
