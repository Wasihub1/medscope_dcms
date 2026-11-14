import React, { useState } from 'react';
import { api } from '../../api/client';
import { Modal } from '../../components/common/Modal';
import { useToast } from '../../context/ToastContext';
import { Referrer } from '../../types';

type Row = Referrer & { registration_no?: string | null; chamber_address?: string | null };

/** Prompt 19: edit a doctor / 3rd party's own details in place (PATCH). Commission is not shown or changed here. */
export const ReferrerEditModal: React.FC<{ referrer: Row; onClose: () => void; onSaved: () => void }> = ({ referrer, onClose, onSaved }) => {
  const { showToast } = useToast();
  const [f, setF] = useState({
    name: referrer.name ?? '',
    referrer_type: referrer.referrer_type ?? 'Doctor',
    phone: referrer.phone ?? '',
    registration_no: referrer.registration_no ?? '',
    specialty: referrer.specialty ?? '',
    chamber_address: referrer.chamber_address ?? '',
  });
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.updateReferrer(referrer.id, { ...f, phone: f.phone || null, registration_no: f.registration_no || null, specialty: f.specialty || null, chamber_address: f.chamber_address || null });
      showToast({ type: 'success', title: 'Saved', message: `${f.name} was updated. Saved bills and reports keep what they already captured.` });
      onSaved();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Save failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const input = 'w-full p-2 bg-white border border-[#CAC7BE] rounded-xl text-xs';
  return (
    <Modal isOpen onClose={onClose} title="Edit doctor / 3rd party" subtitle="Changes this record's own details. Rates and commission are not edited here." maxWidth="md">
      <form onSubmit={save} className="space-y-3 text-xs" data-testid="referrer-edit-form">
        <label className="block font-semibold">Name *<input className={input} value={f.name} onChange={set('name')} required minLength={2} data-testid="edit-ref-name" /></label>
        <label className="block font-semibold">Type
          <select className={input} value={f.referrer_type} onChange={set('referrer_type')} data-testid="edit-ref-type">
            {['Doctor', 'Third Party', ...(['Doctor', 'Third Party'].includes(f.referrer_type) ? [] : [f.referrer_type])].map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="block font-semibold">Phone<input className={input} value={f.phone} onChange={set('phone')} data-testid="edit-ref-phone" /></label>
        <label className="block font-semibold">Registration no.<input className={input} value={f.registration_no} onChange={set('registration_no')} data-testid="edit-ref-reg" /></label>
        <label className="block font-semibold">Specialty<input className={input} value={f.specialty} onChange={set('specialty')} /></label>
        <label className="block font-semibold">Chamber<input className={input} value={f.chamber_address} onChange={set('chamber_address')} /></label>
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="px-4 py-2 font-semibold text-[#54524A] rounded-xl hover:bg-[#E8E7E3]">Cancel</button>
          <button type="submit" disabled={busy || f.name.trim().length < 2} data-testid="edit-ref-save" className="px-5 py-2 font-bold bg-[#525333] text-white rounded-xl disabled:opacity-50">{busy ? 'Saving...' : 'Save'}</button>
        </div>
      </form>
    </Modal>
  );
};
