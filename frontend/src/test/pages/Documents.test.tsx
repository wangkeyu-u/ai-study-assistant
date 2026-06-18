import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Documents from '../../pages/Documents';

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
});
