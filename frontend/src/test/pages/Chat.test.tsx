import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Chat from '../../pages/Chat';

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
});
