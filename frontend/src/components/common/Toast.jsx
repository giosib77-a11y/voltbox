import { createPortal } from 'react-dom';
import { AlertCircle, CheckCircle2, Info, X } from 'lucide-react';
import { useToast } from '../../context/ToastContext.jsx';

/**
 * Toast-ების ვიზუალური კონტეინერი.
 * მდგომარეობას მართავს ToastContext — ეს კომპონენტი მხოლოდ ხატავს.
 */

const STYLES = {
  success: {
    icon: CheckCircle2,
    wrapper: 'border-success-500/30 bg-surface',
    iconClass: 'text-success-600',
  },
  error: {
    icon: AlertCircle,
    wrapper: 'border-danger-500/30 bg-surface',
    iconClass: 'text-danger-fg',
  },
  info: {
    icon: Info,
    wrapper: 'border-primary-500/30 bg-surface',
    iconClass: 'text-primary-700',
  },
};

export default function ToastViewport() {
  const { toasts, dismiss } = useToast();

  if (typeof document === 'undefined') return null;

  return createPortal(
    <div
      className="pointer-events-none fixed inset-x-0 bottom-0 z-toast flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:items-end"
      role="region"
      aria-label="შეტყობინებები"
      // The live region is the container, not the toast.
      //
      // A screen reader announces changes *inside* a region that already
      // existed. `aria-live` used to sit on each toast, which is created at the
      // same moment as its text - so there was no change to announce, and NVDA,
      // JAWS and VoiceOver said nothing. This element is mounted in Layout for
      // the life of the page, so a toast dropped into it is a change.
      //
      // Not `role="status"`, whose implicit aria-atomic is true: that would
      // re-read every toast still on screen each time one arrives.
      aria-live="polite"
      aria-atomic="false"
    >
      {toasts.map((toast) => {
        const style = STYLES[toast.type] || STYLES.info;
        const Icon = style.icon;

        return (
          <div
            key={toast.id}
            className={`pointer-events-auto flex w-full max-w-sm animate-slide-up items-start gap-3 rounded-card border px-4 py-3 shadow-popover ${style.wrapper}`}
          >
            <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${style.iconClass}`} aria-hidden="true" />

            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink-900">{toast.message}</p>
              {toast.action && (
                <button
                  type="button"
                  onClick={() => {
                    toast.action.onClick?.();
                    dismiss(toast.id);
                  }}
                  className="mt-1 text-sm font-semibold text-primary-700 underline-offset-4 hover:underline"
                >
                  {toast.action.label}
                </button>
              )}
            </div>

            <button
              type="button"
              onClick={() => dismiss(toast.id)}
              aria-label="შეტყობინების დახურვა"
              className="-mr-1 -mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-control text-ink-500 transition-colors hover:bg-ink-100 hover:text-ink-700"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>,
    document.body,
  );
}
