import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from '../../App';

describe('App', () => {
  it('renders navigation sidebar', () => {
    render(<App />);
    expect(document.querySelector('nav')).toBeTruthy();
  });

  it('renders main content area', () => {
    render(<App />);
    expect(document.querySelector('main')).toBeTruthy();
  });

  it('renders without crashing', () => {
    const { container } = render(<App />);
    expect(container.firstChild).toBeTruthy();
  });
});
