/**
 * ConfirmDialog: a confirmation before something hard to undo.
 *
 * What it does: states what will happen, in the same words as the button that
 * opened it, and keeps the confirm button busy while the action runs.
 * Where it fits: archiving a product, deleting a category or brand, cancelling
 * an order.
 * Notes: the description is a prop rather than a generic "are you sure?" - the
 * whole value of the dialog is telling the reader what the consequence is.
 */

import { useState } from 'react';

import Modal from '../../components/common/Modal.jsx';
import Button from '../../components/common/Button.jsx';

export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'დადასტურება',
  cancelLabel = 'გაუქმება',
  variant = 'danger',
  onConfirm,
  onClose,
}) {
  const [busy, setBusy] = useState(false);

  async function handleConfirm() {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={busy ? () => {} : onClose} title={title}>
      <div className="p-5">
        <p className="text-sm text-ink-600">{description}</p>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="outline" size="sm" onClick={onClose} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button variant={variant} size="sm" onClick={handleConfirm} loading={busy}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
