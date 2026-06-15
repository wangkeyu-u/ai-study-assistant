import { render, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Chat from '../../pages/Chat';

describe('Chat Page', () => {
  it('renders without crashing', () => {
    const { container } = render(<Chat />);
    expect(container.firstChild).toBeTruthy();
  });

  it('shows message input area', async () => {
    render(<Chat />);
    await waitFor(() => {
      const textarea = document.querySelector('textarea');
      expect(textarea).toBeTruthy();
    });
  });
});
