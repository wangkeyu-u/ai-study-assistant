import { render, waitFor } from '@testing-library/react';
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
});
