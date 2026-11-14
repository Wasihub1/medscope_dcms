import React, { useCallback, useEffect, useState } from 'react';
import { Trash2, RotateCcw, Pencil } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { DeletedItem, Referrer, TestItem } from '../../types';
import { ReferenceRangesPanel } from './ReferenceRangesPanel';
import { ReferrerEditModal } from './ReferrerEditModal';

/**
 * Prompt 11: one shared screen for the soft-delete workflow of Tests and Doctors / 3rd parties,
 * plus the shared "Deleted" view (Users, Doctors / 3rd parties, Tests) with Restore.
 * Delete only hides the row from NEW selection; old bills, lines and results are untouched.
 */
type Tab = 'TESTS' | 'REFERRERS' | 'RANGES' | 'DELETED';
type Pending =
  | { mode: 'delete'; kind: 'TEST' | 'REFERRER'; id: number | string; name: string }
  | { mode: 'restore'; item: DeletedItem }
  | null;

const KIND_LABEL: Record<string, string> = { USER: 'User', REFERRER: 'Doctor / 3rd party', TEST: 'Test' };

const delBtn =
  'inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#9B2C2C] bg-white border border-[#E5B9B9] hover:bg-[#FBEFEF] rounded-lg cursor-pointer';
const restoreBtn =
  'inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold text-[#525333] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-lg cursor-pointer';

export const CatalogAdminPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const canTests = hasPermission('test_catalog.manage');
  const canRefs = hasPermission('referrer.manage');
  const canUsers = hasPermission('user.manage');
  const canAny = canTests || canRefs || canUsers;
  const [tab, setTab] = useState<Tab>(canTests ? 'TESTS' : canRefs ? 'REFERRERS' : 'DELETED');
  const [search, setSearch] = useState('');
  const [tests, setTests] = useState<TestItem[]>([]);
  const [refs, setRefs] = useState<Referrer[]>([]);
  const [editing, setEditing] = useState<Referrer | null>(null);
  const [deleted, setDeleted] = useState<DeletedItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<Pending>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      if (tab === 'TESTS' && canTests) setTests(await api.getTests(search || undefined, undefined, 200));
      if (tab === 'REFERRERS' && canRefs) setRefs(await api.getReferrers(search || undefined));
      if (tab === 'DELETED') {
        const parts = await Promise.all([
          canUsers ? api.getDeletedUsers() : Promise.resolve([] as DeletedItem[]),
          canRefs ? api.getDeletedReferrers() : Promise.resolve([] as DeletedItem[]),
          canTests ? api.getDeletedTests() : Promise.resolve([] as DeletedItem[]),
        ]);
        setDeleted(parts.flat().sort((a, b) => b.deleted_at.localeCompare(a.deleted_at)));
      }
    } catch (err: any) {
      showToast({ type: 'error', title: 'Could not load', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [tab, search, canTests, canRefs, canUsers, showToast]);

  useEffect(() => {
    if (canAny) load();
  }, [canAny, load]);

  if (!canAny) {
    return <div className="p-8 text-sm text-[#6D6A60]" data-testid="catalog-admin-denied">You do not have access to this page.</div>;
  }

  const confirm = async (reason: string) => {
    if (!pending) return;
    setBusy(true);
    try {
      if (pending.mode === 'delete') {
        if (pending.kind === 'TEST') await api.deleteTest(pending.id, reason);
        else await api.deleteReferrer(pending.id, reason);
        showToast({ type: 'success', title: 'Deleted', message: `${pending.name} is hidden from new selection. Restore it from the Deleted tab.` });
      } else {
        const it = pending.item;
        if (it.kind === 'TEST') await api.restoreTest(it.id);
        else if (it.kind === 'REFERRER') await api.restoreReferrer(it.id);
        else await api.restoreUser(it.id);
        showToast({ type: 'success', title: 'Restored', message: it.title });
      }
      setPending(null);
      await load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Action failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const tabBtn = (t: Tab, label: string, show: boolean) =>
    show ? (
      <button
        key={t}
        onClick={() => { setTab(t); setSearch(''); }}
        data-testid={`catalog-tab-${t.toLowerCase()}`}
        className={`px-4 py-2 text-xs font-semibold rounded-lg cursor-pointer ${tab === t ? 'bg-[#525333] text-white' : 'bg-white border border-[#CAC7BE] text-[#525333]'}`}
      >
        {label}
      </button>
    ) : null;

  return (
    <div className="p-6 space-y-5 max-w-6xl mx-auto" data-testid="catalog-admin-page">
      <div>
        <h1 className="text-xl font-semibold text-[#1B1B0E]">Catalog &amp; Deleted Items</h1>
        <p className="text-xs text-[#6D6A60] mt-1">
          Delete hides a test, doctor or 3rd party from new selection only. Existing bills and results keep their saved details.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {tabBtn('TESTS', 'Tests', canTests)}
        {tabBtn('REFERRERS', 'Doctors & 3rd parties', canRefs)}
        {tabBtn('RANGES', 'Reference ranges', canTests)}
        {tabBtn('DELETED', 'Deleted', true)}
      </div>
      {tab === 'RANGES' && <ReferenceRangesPanel />}

      {tab !== 'DELETED' && tab !== 'RANGES' && (
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search…"
          data-testid="catalog-search"
          className="w-full max-w-sm px-3 py-2 border border-[#CAC7BE] rounded-lg bg-white text-xs"
        />
      )}
      {loading && <p className="text-xs text-[#6D6A60]">Loading…</p>}

      {tab === 'TESTS' && (
        <table className="w-full text-xs bg-white border border-[#E8E7E3] rounded-xl overflow-hidden">
          <thead className="bg-[#F4F3F0] text-left">
            <tr><th className="p-2">Code</th><th className="p-2">Name</th><th className="p-2">Department</th><th className="p-2 text-right">Action</th></tr>
          </thead>
          <tbody>
            {tests.map((t) => (
              <tr key={t.id} className="border-t border-[#E8E7E3]">
                <td className="p-2">{t.code}</td>
                <td className="p-2">{t.name}</td>
                <td className="p-2">{t.department}</td>
                <td className="p-2 text-right">
                  <button
                    className={delBtn}
                    data-testid={`delete-test-${t.id}`}
                    onClick={() => setPending({ mode: 'delete', kind: 'TEST', id: t.id, name: `Test [${t.code}] ${t.name}` })}
                  >
                    <Trash2 className="w-3 h-3" /> Delete
                  </button>
                </td>
              </tr>
            ))}
            {!loading && tests.length === 0 && <tr><td colSpan={4} className="p-4 text-center text-[#6D6A60]">No tests found.</td></tr>}
          </tbody>
        </table>
      )}

      {tab === 'REFERRERS' && (
        <table className="w-full text-xs bg-white border border-[#E8E7E3] rounded-xl overflow-hidden">
          <thead className="bg-[#F4F3F0] text-left">
            <tr><th className="p-2">Name</th><th className="p-2">Type</th><th className="p-2">Phone</th><th className="p-2 text-right">Action</th></tr>
          </thead>
          <tbody>
            {refs.map((r) => (
              <tr key={r.id} className="border-t border-[#E8E7E3]">
                <td className="p-2">{r.name}</td>
                <td className="p-2">{r.referrer_type}</td>
                <td className="p-2">{r.phone}</td>
                <td className="p-2 text-right space-x-2">
                  <button className={restoreBtn} data-testid={`edit-referrer-${r.id}`} onClick={() => setEditing(r)}>
                    <Pencil className="w-3 h-3" /> Edit
                  </button>
                  <button
                    className={delBtn}
                    data-testid={`delete-referrer-${r.id}`}
                    onClick={() => setPending({ mode: 'delete', kind: 'REFERRER', id: r.id, name: `${r.referrer_type || 'Referrer'} ${r.name}` })}
                  >
                    <Trash2 className="w-3 h-3" /> Delete
                  </button>
                </td>
              </tr>
            ))}
            {!loading && refs.length === 0 && <tr><td colSpan={4} className="p-4 text-center text-[#6D6A60]">No doctors or 3rd parties found.</td></tr>}
          </tbody>
        </table>
      )}

      {tab === 'DELETED' && (
        <table className="w-full text-xs bg-white border border-[#E8E7E3] rounded-xl overflow-hidden" data-testid="deleted-table">
          <thead className="bg-[#F4F3F0] text-left">
            <tr>
              <th className="p-2">Type</th><th className="p-2">Item</th><th className="p-2">Deleted by</th>
              <th className="p-2">When</th><th className="p-2">Reason</th><th className="p-2 text-right">Action</th>
            </tr>
          </thead>
          <tbody>
            {deleted.map((d) => (
              <tr key={`${d.kind}-${d.id}`} className="border-t border-[#E8E7E3]">
                <td className="p-2">{KIND_LABEL[d.kind]}</td>
                <td className="p-2"><div className="font-semibold">{d.title}</div><div className="text-[#6D6A60]">{d.subtitle}</div></td>
                <td className="p-2">{d.deleted_by_name || '—'}</td>
                <td className="p-2">{new Date(d.deleted_at).toLocaleString()}</td>
                <td className="p-2">{d.delete_reason}</td>
                <td className="p-2 text-right">
                  <button className={restoreBtn} data-testid={`restore-${d.kind.toLowerCase()}-${d.id}`} onClick={() => setPending({ mode: 'restore', item: d })}>
                    <RotateCcw className="w-3 h-3" /> Restore
                  </button>
                </td>
              </tr>
            ))}
            {!loading && deleted.length === 0 && <tr><td colSpan={6} className="p-4 text-center text-[#6D6A60]">Nothing has been deleted.</td></tr>}
          </tbody>
        </table>
      )}

      <ConfirmDialog
        isOpen={pending !== null}
        title={pending?.mode === 'restore' ? 'Restore item?' : 'Delete item?'}
        itemName={pending ? (pending.mode === 'delete' ? pending.name : `${KIND_LABEL[pending.item.kind]}: ${pending.item.title}`) : ''}
        effect={
          pending?.mode === 'restore'
            ? 'This makes the item selectable again for new work.'
            : pending?.kind === 'TEST'
              ? 'This hides the test from new billing. Existing invoices keep their saved price and are not affected.'
              : 'This hides it from new selection. Existing bills, referrals and commission records are not affected.'
        }
        confirmLabel={pending?.mode === 'restore' ? 'Restore' : 'Delete'}
        requireReason={pending?.mode === 'delete'}
        danger={pending?.mode === 'delete'}
        busy={busy}
        testId="catalog-confirm"
        onCancel={() => setPending(null)}
        onConfirm={confirm}
      />
      {editing && <ReferrerEditModal referrer={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
};
