import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import Home from '../../pages/Home';
import { server } from '../mocks/server';

describe('Home Page', () => {
  it('shows recent sources and conversations as resumable work', async () => {
    server.use(
      http.get('/api/documents', () =>
        HttpResponse.json({
          documents: [
            {
              id: 'doc-recent',
              filename: 'research.pdf',
              file_type: 'pdf',
              file_size: 100,
              chunk_count: 12,
              status: 'ready',
              tags: [],
              created_at: '2026-01-01',
            },
          ],
        })
      ),
      http.get('/api/chat/sessions', () =>
        HttpResponse.json([
          {
            id: 'session-recent',
            title: 'Hybrid retrieval notes',
            message_count: 4,
            created_at: '2026-01-01',
            updated_at: '2026-01-01',
          },
        ])
      )
    );

    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    );

    expect(await screen.findByText('research.pdf')).toBeInTheDocument();
    expect(await screen.findByText('Hybrid retrieval notes')).toBeInTheDocument();
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });
});
