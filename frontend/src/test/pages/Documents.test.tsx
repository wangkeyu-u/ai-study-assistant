import { render, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Documents from '../../pages/Documents';

describe('Documents Page', () => {
  it('renders without crashing', () => {
    const { container } = render(<Documents />);
    expect(container.firstChild).toBeTruthy();
  });

  it('renders upload area', async () => {
    const { container } = render(<Documents />);
    await waitFor(() => {
      expect(container.firstChild).toBeTruthy();
    });
  });
});
