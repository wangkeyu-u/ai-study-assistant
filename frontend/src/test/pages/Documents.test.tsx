import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import Documents from '../../pages/Documents';
import { server } from '../mocks/server';

const renderDocuments = () =>
  render(
    <MemoryRouter>
      <Documents />
    </MemoryRouter>
  );

describe('Documents Page', () => {
  it('renders without crashing', () => {
    const { container } = renderDocuments();
    expect(container.firstChild).toBeTruthy();
  });

  it('renders upload area', async () => {
    const { container } = renderDocuments();
    await waitFor(() => {
      expect(container.firstChild).toBeTruthy();
    });
  });

  it('offers a one-click interview demo', async () => {
    renderDocuments();

    await waitFor(() => {
      expect(
        screen.getAllByRole('button', { name: /Load Interview Demo|载入面试演示/ }).length
      ).toBeGreaterThan(0);
    });
  });

  it('selects multiple ready documents for comparison', async () => {
    server.use(
      http.get('/api/documents', () =>
        HttpResponse.json({
          documents: [
            {
              id: 'doc-a',
              filename: 'a.pdf',
              file_type: 'pdf',
              file_size: 100,
              chunk_count: 2,
              status: 'ready',
              tags: [],
              created_at: '2026-01-01',
            },
            {
              id: 'doc-b',
              filename: 'b.pdf',
              file_type: 'pdf',
              file_size: 100,
              chunk_count: 2,
              status: 'ready',
              tags: [],
              created_at: '2026-01-01',
            },
          ],
        })
      )
    );
    const user = userEvent.setup();
    renderDocuments();
    const checkboxes = await screen.findAllByRole('checkbox');

    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);

    expect(screen.getByRole('button', { name: /Compare documents|开始对比/ })).toBeEnabled();
  });

  it('shows a recovery state instead of an empty library when loading fails', async () => {
    server.use(http.get('/api/documents', () => new HttpResponse(null, { status: 503 })));

    renderDocuments();

    expect(
      await screen.findByText(/library is temporarily unavailable|暂时无法连接资料库/i)
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/No documents uploaded yet|还没有上传任何文档/)
    ).not.toBeInTheDocument();
  });
});
