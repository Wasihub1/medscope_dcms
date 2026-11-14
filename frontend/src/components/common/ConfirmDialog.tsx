import React, { useEffect, useState } from 'react';
import { Modal } from './Modal';

/**
 * Prompt 11: the one reusable confirm dialog for destructive / semi-destructive actions
 * (soft delete with a required reason, restore, draft discard). It names the exact item,
 * states the effect in one sentence, and enables Confirm only when the reason (if required) is filled.
 */
export const isConfirmReady = (requireReason: boolean, reason: string, busy: boolean): boolean =>
  !busy && (!requireReason || reason.trim().length > 0);

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  /** Exact item being acted on, e.g. "Test [CBC] Complete Blood Count". */
  itemName: string;
  /** One short sentence describing the effect. */
  effect: string;
  confirmLabel: string;
  requireReason?: boolean;
  busy?: boolean;
  danger?: boolean;
  testId?: string;
  onCancel: () => void;
  onConfirm: (reason: string) => void | Promise<void>;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen, title, itemName, effect, confirmLabel, requireReason = false, busy = false, danger = false,
  testId = 'confirm-dialog', onCancel, onConfirm,
}) => {
  const [reason, setReason] = useState('');
  useEffect(() => {
    if (isOpen) setReason('');
  }, [isOpen, itemName]);

  const ready = isConfirmReady(requireReason, reason, busy);
  return (
    <Modal isOpen={isOpen} onClose={onCancel} title={title} maxWidth="sm">
      <div className="space-y-4 text-xs text-[#54524A]" data-testid={testId}>
        <p className="text-sm font-semibold text-[#1B1B0E]" data-testid={`${testId}-item`}>{itemName}</p>
        <p>{effect}</p>
        {requireReason && (
          <div>
            <label className="block font-semibold text-[#1B1B0E] mb-1" htmlFor={`${testId}-reason`}>Reason (required)</label>
            <textarea
              id={`${testId}-reason`}
              value={reason}
              maxLength={500}
              rows={3}
              onChange={(e) => setReason(e.target.value)}
              data-testid={`${testId}-reason`}
              className="w-full px-3 py-2 border border-[#CAC7BE] rounded-lg bg-white text-xs focus:outline-none focus:ring-2 focus:ring-[#525333]/30"
              placeholder="Why is this being removed?"
            />
          </div>
        )}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onCancel} data-testid={`${testId}-cancel`}
            className="px-3 py-1.5 text-xs font-semibold text-[#525333] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-lg cursor-pointer">
            Cancel
          </button>
          <button type="button" disabled={!ready} onClick={() => onConfirm(reason.trim())} data-testid={`${testId}-confirm`}
            className={`px-3 py-1.5 text-xs font-semibold text-white rounded-lg cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${danger ? 'bg-[#9B2C2C] hover:bg-[#7F2323]' : 'bg-[#525333] hover:bg-[#3F4026]'}`}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
};
