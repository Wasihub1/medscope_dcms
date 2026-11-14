import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Download } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { AuditLogItem, AuditLogMeta, AuditLogPage as Page, AuditLogQuery } from '../../types';

/**
 * Module 23 audit viewer (Prompt 11 slice, completed in Prompt 19B). View only: filter by domain, action, entity,
 * actor, acting role and date range, free-text search across action / entity / before / after, and a CSV export of
 * exactly the rows the current filters select. Nothing on this screen can change an audit row.
 */
export const AuditLogPage: React.FC = () => {
  const { hasPermission } = useAuth();
  const { showToast } = useToast();
  const [meta, setMeta] = useState<AuditLogMeta>({ actions: [], entity_types: [], domains: [], roles: [], actors: [] });
  const [domain, setDomain] = useState('');
  const [action, setAction] = useState('');
  const [entityType, setEntityType] = useState('');
  const [actorId, setActorId] = useState('');
  const [role, setRole] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [search, setSearch] = useState('');
  const [q, setQ] = useState(''); // the search text actually applied (debounced)
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Page | null>(null);
  const [open, setOpen] = useState<AuditLogItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const allowed = hasPermission('audit.view');

  const filters = useMemo<AuditLogQuery>(() => ({
    domain, action, entity_type: entityType, actor_id: actorId ? Number(actorId) : undefined,
    acting_role: role, q, date_from: from, date_to: to,
  }), [domain, action, entityType, actorId, role, q, from, to]);
  const domainLabel = useMemo(() => Object.fromEntries(meta.domains.map((d) => [d.key, d.label])), [meta.domains]);
  const anyFilter = Boolean(domain || action || entityType || actorId || role || q || from || to || search);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.getAuditLogs({ ...filters, page, size: 50 }));
    } catch (err: any) {
      showToast({ type: 'error', title: 'Could not load audit log', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [filters, page, showToast]);

  useEffect(() => { if (allowed) api.getAuditMeta().then(setMeta).catch(() => undefined); }, [allowed]);
  useEffect(() => { if (allowed) load(); }, [allowed, load]);
  useEffect(() => {
    const t = setTimeout(() => { setQ(search.trim()); setPage(1); }, 350);
    return () => clearTimeout(t);
  }, [search]);

  if (!allowed) {
    return <div className="p-8 text-sm text-[#6D6A60]" data-testid="audit-denied">You do not have access to the audit log.</div>;
  }
  const inp = 'px-3 py-2 border border-[#CAC7BE] rounded-lg bg-white text-xs';
  const onFilter = (fn: (v: string) => void) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    fn(e.target.value);
    setPage(1);
  };
  const clearAll = () => {
    setDomain(''); setAction(''); setEntityType(''); setActorId(''); setRole(''); setFrom(''); setTo(''); setSearch(''); setQ(''); setPage(1);
  };
  const exportCsv = async () => {
    setExporting(true);
    try {
      await api.downloadAuditCsv(filters);
      showToast({ type: 'success', title: 'Export ready', message: 'The CSV holds every row the current filters select. The export was recorded in the audit log.' });
      load(); // the export wrote its own audit row
    } catch (err: any) {
      showToast({ type: 'error', title: 'Export failed', message: err.message });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="p-6 space-y-4 max-w-7xl mx-auto" data-testid="audit-log-page">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[#1B1B0E]">Audit Log</h1>
          <p className="text-xs text-[#6D6A60] mt-1">Read only, newest first. Rows are kept forever and cannot be changed or deleted by anyone.</p>
        </div>
        <button onClick={exportCsv} disabled={exporting} data-testid="audit-export"
          className="px-4 py-2 bg-[#525333] hover:bg-[#3F4026] disabled:opacity-60 text-white text-xs font-semibold rounded-lg inline-flex items-center gap-1.5 cursor-pointer">
          <Download className="w-4 h-4" /> {exporting ? 'Exporting…' : 'Export CSV (current filters)'}
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        <input className={`${inp} w-64`} placeholder="Search action, entity, before / after text" value={search}
          onChange={(e) => setSearch(e.target.value)} data-testid="audit-search" />
        <select className={inp} value={domain} onChange={onFilter(setDomain)} data-testid="audit-filter-domain">
          <option value="">All domains</option>
          {meta.domains.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
        </select>
        <select className={inp} value={action} onChange={onFilter(setAction)} data-testid="audit-filter-action">
          <option value="">All actions</option>
          {meta.actions.map((a) => <option key={a}>{a}</option>)}
        </select>
        <select className={inp} value={entityType} onChange={onFilter(setEntityType)} data-testid="audit-filter-entity">
          <option value="">All entities</option>
          {meta.entity_types.map((a) => <option key={a}>{a}</option>)}
        </select>
        <select className={inp} value={actorId} onChange={onFilter(setActorId)} data-testid="audit-filter-actor">
          <option value="">All people</option>
          {meta.actors.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <select className={inp} value={role} onChange={onFilter(setRole)} data-testid="audit-filter-role">
          <option value="">All roles</option>
          {meta.roles.map((r) => <option key={r}>{r}</option>)}
        </select>
        <input type="date" className={inp} value={from} onChange={onFilter(setFrom)} data-testid="audit-filter-from" aria-label="From date" />
        <input type="date" className={inp} value={to} onChange={onFilter(setTo)} data-testid="audit-filter-to" aria-label="To date" />
        {anyFilter && (
          <button onClick={clearAll} data-testid="audit-clear" className="px-3 py-2 text-xs text-[#525333] underline cursor-pointer">Clear filters</button>
        )}
      </div>
      <table className="w-full text-xs bg-white border border-[#E8E7E3] rounded-xl overflow-hidden">
        <thead className="bg-[#F4F3F0] text-left">
          <tr>
            <th className="p-2">When</th><th className="p-2">Who</th><th className="p-2">Role</th><th className="p-2">Domain</th>
            <th className="p-2">Action</th><th className="p-2">Entity</th><th className="p-2">Reason</th><th className="p-2" />
          </tr>
        </thead>
        <tbody>
          {data?.items.map((r) => (
            <tr key={r.id} className="border-t border-[#E8E7E3]">
              <td className="p-2 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
              <td className="p-2">{r.actor_name || (r.actor_id ? `#${r.actor_id}` : 'System')}</td>
              <td className="p-2">{r.acting_role}</td>
              <td className="p-2">{domainLabel[r.domain] || r.domain}</td>
              <td className="p-2">{r.action}</td>
              <td className="p-2">{r.entity_type} #{r.entity_id}</td>
              <td className="p-2">{r.reason}</td>
              <td className="p-2 text-right">
                <button className="text-[#525333] underline cursor-pointer" onClick={() => setOpen(open?.id === r.id ? null : r)} data-testid={`audit-detail-${r.id}`}>
                  Details
                </button>
              </td>
            </tr>
          ))}
          {!loading && data && data.items.length === 0 && (
            <tr><td colSpan={8} className="p-4 text-center text-[#6D6A60]">No audit rows match.</td></tr>
          )}
        </tbody>
      </table>
      {open && (
        <div className="p-4 bg-white border border-[#E8E7E3] rounded-xl text-xs space-y-2" data-testid="audit-detail-panel">
          <div><span className="font-semibold">Before:</span> {open.before_value || '—'}</div>
          <div><span className="font-semibold">After:</span> {open.after_value || '—'}</div>
        </div>
      )}
      <div className="flex items-center gap-3 text-xs">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-3 py-1.5 border border-[#CAC7BE] rounded-lg bg-white disabled:opacity-50 cursor-pointer">Previous</button>
        <span data-testid="audit-count">Page {data?.page ?? 1} of {data?.pages ?? 1} ({data?.total ?? 0} rows)</span>
        <button disabled={!data || page >= data.pages} onClick={() => setPage(page + 1)} className="px-3 py-1.5 border border-[#CAC7BE] rounded-lg bg-white disabled:opacity-50 cursor-pointer">Next</button>
      </div>
    </div>
  );
};
