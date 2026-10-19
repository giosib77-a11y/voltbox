import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';

import Logo, { LogoMark } from './Logo.jsx';
import { SITE_NAME } from '../../constants/index.js';
import { t } from '../../i18n/index.js';

function renderLogo(props) {
  return render(
    <MemoryRouter>
      <Logo {...props} />
    </MemoryRouter>
  );
}

describe('Logo', () => {
  it('links to the home page under the same accessible name', () => {
    renderLogo();
    const link = screen.getByRole('link', { name: t('layout.logoLabel', { site: SITE_NAME }) });
    expect(link.getAttribute('href')).toBe('/');
  });

  it('draws the mark as an aria-hidden svg and sets the wordmark from SITE_NAME', () => {
    const { container } = renderLogo();
    const svg = container.querySelector('svg');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(screen.getByText(SITE_NAME).textContent).toBe(SITE_NAME);
  });

  it('shows the tagline, and compact hides it', () => {
    const { unmount } = renderLogo();
    expect(screen.getByText(t('site.tagline'))).toBeTruthy();
    unmount();
    renderLogo({ compact: true });
    expect(screen.queryByText(t('site.tagline'))).toBeNull();
  });
});

describe('LogoMark', () => {
  it('takes a size and stays aria-hidden', () => {
    const { container } = render(<LogoMark size={96} />);
    const svg = container.querySelector('svg');
    expect(svg.getAttribute('width')).toBe('96');
    expect(svg.getAttribute('height')).toBe('96');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
  });
});
