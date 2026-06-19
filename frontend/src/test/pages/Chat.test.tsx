import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import Chat from '../../pages/Chat';
import { server } from '../mocks/server';

const renderChat = (initialPath = '/chat') =>
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Chat />
    </MemoryRouter>
  );

describe('Chat Page', () => {
  it('renders without crashing', () => {
    const { container } = renderChat();
    expect(container.firstChild).toBeTruthy();
  });

  it('shows message input area', async () => {
    renderChat();
    await waitFor(() => {
      const textarea = document.querySelector('textarea');
      expect(textarea).toBeTruthy();
    });
  });

  it('prefills a suggested question from the URL', async () => {
    renderChat('/chat?q=How%20does%20hybrid%20retrieval%20work%3F');

    await waitFor(() => {
      expect(document.querySelector('textarea')).toHaveValue('How does hybrid retrieval work?');
    });
  });

  it('keeps a multi-document comparison scope from the URL', async () => {
    renderChat('/chat?documents=doc-a%2Cdoc-b&names=a.pdf%7Cb.pdf&q=Compare');

    await waitFor(() => {
      expect(screen.getByText(/Comparison scope|多文档对比范围/)).toBeInTheDocument();
      expect(screen.getByText('a.pdf · b.pdf')).toBeInTheDocument();
    });
  });

  it('restores a conversation requested from the home page', async () => {
    server.use(
      http.get('/api/chat/sessions/session-1/messages', () =>
        HttpResponse.json([
          {
            id: 'message-1',
            role: 'assistant',
            content: 'Restored grounded answer',
            citations: [],
            created_at: '2026-01-01',
          },
        ])
      )
    );

    renderChat('/chat?session=session-1');

    expect(await screen.findByText('Restored grounded answer')).toBeInTheDocument();
  });
});
