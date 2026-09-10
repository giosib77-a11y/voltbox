import { useCallback, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * უნივერსალური მოდალი / drawer / bottom-sheet.
 *
 * a11y: role="dialog", aria-modal, ESC-ით დახურვა, focus trap და
 * ფოკუსის დაბრუნება გამომძახებელ ელემენტზე დახურვის შემდეგ.
 *
 * @param {{ position?: 'center'|'bottom'|'right'|'left' }} props
 */

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input:not([disabled]), select, [tabindex]:not([tabindex="-1"])';

const POSITIONS = {
  center:
    'items-center justify-center p-4 sm:p-6',
  bottom: 'items-end justify-center',
  right: 'items-stretch justify-end',
  left: 'items-stretch justify-start',
};

const PANELS = {
  center: 'w-full max-w-lg rounded-card animate-slide-up',
  bottom: 'w-full max-h-[88vh] rounded-t-2xl animate-sheet-up',
  right: 'h-full w-[86vw] max-w-sm animate-slide-in-right',
  left: 'h-full w-[86vw] max-w-sm animate-slide-in-left',
};

export default function Modal({
  open,
  onClose,
  title = '',
  children,
  footer = null,
  position = 'center',
  labelledBy,
  panelClassName = '',
  showClose = true,
}) {
  const panelRef = useRef(null);
  const previouslyFocused = useRef(null);

  const handleKeyDown = useCallback(
    (event) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        onClose?.();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;

      const nodes = Array.from(panelRef.current.querySelectorAll(FOCUSABLE)).filter(
        (node) => node.offsetParent !== null,
      );
      if (nodes.length === 0) {
        event.preventDefault();
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    },
    [onClose],
  );

  useEffect(() => {
    if (!open) return undefined;

    previouslyFocused.current = document.activeElement;
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';

    const timer = setTimeout(() => {
      const target = panelRef.current?.querySelector(FOCUSABLE);
      (target || panelRef.current)?.focus();
    }, 30);

    return () => {
      clearTimeout(timer);
      document.body.style.overflow = overflow;
      if (previouslyFocused.current instanceof HTMLElement) previouslyFocused.current.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className={`fixed inset-0 z-modal flex ${POSITIONS[position] || POSITIONS.center}`}
      onKeyDown={handleKeyDown}
    >
      <button
        type="button"
        aria-label="დახურვა"
        tabIndex={-1}
        className="absolute inset-0 cursor-default bg-ink-950/50 animate-fade-in"
        onClick={onClose}
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={!labelledBy && title ? title : undefined}
        aria-labelledby={labelledBy}
        tabIndex={-1}
        className={`relative flex flex-col overflow-hidden bg-white shadow-popover focus:outline-none ${
          PANELS[position] || PANELS.center
        } ${panelClassName}`}
      >
        {(title || showClose) && (
          <div className="flex shrink-0 items-center justify-between gap-4 border-b border-ink-200 px-5 py-4">
            {title ? <h2 className="text-base font-semibold text-ink-900">{title}</h2> : <span />}
            {showClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="დახურვა"
                className="-mr-1.5 flex h-9 w-9 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-800"
              >
                <X className="h-5 w-5" aria-hidden="true" />
              </button>
            )}
          </div>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>

        {footer && <div className="shrink-0 border-t border-ink-200 bg-white p-4">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
