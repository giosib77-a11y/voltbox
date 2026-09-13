/**
 * Tests for the toast viewport, as a screen reader meets it.
 *
 * A live region only announces changes that happen *inside* it. A region that
 * arrives in the document with its text already in place is a new element, not
 * a change, and NVDA, JAWS and VoiceOver routinely say nothing at all.
 *
 * That is what this file pins. `aria-live` used to sit on each toast, which is
 * created at the same moment as its message - so "პროდუქტი დაემატა კალათაში",
 * "შეკვეთა გაფორმდა" and every error toast were silent. The region has to be
 * the container, which is mounted in Layout for the life of the page, and the
 * toasts have to be plain content dropped into it.
 */

import { describe, expect, it } from 'vitest';
import { act, render, screen } from '@testing-library/react';

import ToastViewport from './Toast.jsx';
import { ToastProvider } from '../../context/ToastContext.jsx';
import { useToast } from '../../hooks/useToast.js';

let toast;

function Harness() {
  toast = useToast();
  return null;
}

function renderToasts() {
  return render(
    <ToastProvider>
      <Harness />
      <ToastViewport />
    </ToastProvider>,
  );
}

const liveRegion = () => document.querySelector('[aria-live]');

describe('the toast viewport', () => {
  it('is a live region before anything is announced in it', () => {
    // The whole point: the region has to already be there when the message
    // arrives, or the message is not a change to anything.
    renderToasts();

    const region = liveRegion();
    expect(region).not.toBeNull();
    expect(region.getAttribute('aria-live')).toBe('polite');
    expect(region.textContent).toBe('');
  });

  it('puts the message inside that same region', () => {
    renderToasts();
    const region = liveRegion();

    act(() => {
      toast.success('პროდუქტი დაემატა კალათაში');
    });

    expect(screen.getByText('პროდუქტი დაემატა კალათაში')).toBeInTheDocument();
    expect(region.contains(screen.getByText('პროდუქტი დაემატა კალათაში'))).toBe(true);
  });

  it('never gives a toast a live region of its own', () => {
    // A nested one is the bug this file exists for: it is created with its
    // content, so it announces nothing, and it also shadows the container.
    renderToasts();

    act(() => {
      toast.error('რაღაც ვერ მოხერხდა');
    });

    expect(document.querySelectorAll('[aria-live]')).toHaveLength(1);
    expect(document.querySelectorAll('[role="status"]').length).toBeLessThanOrEqual(1);
  });

  it('announces a second message without replacing the first', () => {
    // aria-atomic stays off, so a reader is told what was added rather than
    // having every toast on screen read out again.
    renderToasts();

    act(() => {
      toast.info('პირველი');
      toast.info('მეორე');
    });

    expect(liveRegion().getAttribute('aria-atomic')).not.toBe('true');
    expect(screen.getByText('პირველი')).toBeInTheDocument();
    expect(screen.getByText('მეორე')).toBeInTheDocument();
  });

  it('still names the region for somebody browsing landmarks', () => {
    renderToasts();

    expect(liveRegion()).toHaveAccessibleName('შეტყობინებები');
  });
});
