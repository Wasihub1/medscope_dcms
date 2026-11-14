import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Loader2, Plus, ShieldCheck, UserCog, Users as UsersIcon, KeyRound, Power, Pencil, Lock, Trash2 } from 'lucide-react';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { useToast } from '../../context/ToastContext';
import { Modal } from '../../components/common/Modal';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { ManagedUser, ManagedUserDetail, UserAdminMeta } from '../../types';

/**
 * Prompt 10D Part 5 — Owner/Admin user management ("Create User" tab + user list).
 * Visible only with the 'user.manage' permission. One login = one fixed role.
 * The server enforces every safety rule; this screen only mirrors them for clarity.
 */

type OverrideMap = Record<string, boolean>;

const inputCls =
  'w-full bg-white border border-[#CAC7BE] rounded-xl px-3 py-2 text-xs text-[#1B1B0E] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#CF8852]';
const labelCls = 'block text-[11px] font-semibold text-[#54524A] mb-1';
const btnPrimary =
  'inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-bold text-[#26270F] bg-[#CF8852] hover:bg-[#B7703B] hover:text-white rounded-xl transition-colors cursor-pointer disabled:opacity-50';
const btnSecondary =
  'inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#525333] bg-white border border-[#CAC7BE] hover:bg-[#F4F3F0] rounded-xl transition-colors cursor-pointer disabled:opacity-50';

/** Permission editor: role defaults with per-user add/remove toggles. */
const PermissionEditor: React.FC<{
  meta: UserAdminMeta;
  role: string;
  overrides: OverrideMap;
  onChange: (next: OverrideMap) => void;
  disabled?: boolean;
}> = ({ meta, role, overrides, onChange, disabled }) => {
  const defaults = useMemo(() => new Set(meta.role_defaults[role] || []), [meta, role]);
  const moneyRestricted = meta.money_restricted_roles.includes(role);
  const groups = useMemo(() => {
    const g: Record<string, typeof meta.permissions> = {};
    meta.permissions.forEach((p) => {
      (g[p.group] = g[p.group] || []).push(p);
    });
    return g;
  }, [meta]);

  const toggle = (key: string) => {
    const isDefault = defaults.has(key);
    const effective = key in overrides ? overrides[key] : isDefault;
    const next = { ...overrides };
    const target = !effective;
    if (target === isDefault) delete next[key];
    else next[key] = target;
    onChange(next);
  };

  return (
    <div className="space-y-3" data-testid="permission-editor">
      {moneyRestricted && (
        <p className="text-[11px] text-[#8A5608] bg-[#FEF7EC] border border-[#FBE0B2] rounded-xl px-3 py-2">
          {role} can never see money. Money permissions are locked off for this role.
        </p>
      )}
      {Object.entries(groups).map(([group, perms]) => (
        <div key={group}>
          <span className="block text-[10px] font-bold uppercase tracking-wider text-[#8E8A7E] mb-1">{group}</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
            {perms.map((p) => {
              const isDefault = defaults.has(p.key);
              const overridden = p.key in overrides;
              const locked = moneyRestricted && p.exposes_money;
              const effective = locked ? false : overridden ? overrides[p.key] : isDefault;
              return (
                <label
                  key={p.key}
                  className={`flex items-start gap-2 px-2.5 py-1.5 rounded-lg border text-[11px] ${
                    overridden ? 'border-[#CF8852] bg-[#FDF6EF]' : 'border-[#E4E2DC] bg-white'
                  } ${locked ? 'opacity-50' : ''}`}
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 accent-[#525333]"
                    checked={effective}
                    disabled={disabled || locked}
                    onChange={() => toggle(p.key)}
                    data-testid={`perm-${p.key}`}
                  />
                  <span className="min-w-0">
                    <span className="block font-semibold text-[#1B1B0E] break-words">{p.label}</span>
                    <span className="block text-[10px] text-[#8E8A7E] break-all">
                      {p.key} · {locked ? 'locked (money)' : overridden ? (overrides[p.key] ? 'added for this user' : 'removed for this user') : isDefault ? 'role default' : 'not in role'}
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

const emptyForm = {
  display_name: '',
  username: '',
  phone: '',
  email: '',
  department: '',
  password: '',
  role: 'RECEPTIONIST',
  lab_section: '',
  doctor_profile_id: '',
  active: true,
};

export const UserManagementPage: React.FC = () => {
  const { hasPermission, user } = useAuth();
  const { showToast } = useToast();
  const [tab, setTab] = useState<'list' | 'create'>('list');
  const [meta, setMeta] = useState<UserAdminMeta | null>(null);
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  // Prompt 15: doctor profiles a DOCTOR login can be linked to (name + registration no. are printed on reports)
  const [doctorOptions, setDoctorOptions] = useState<{ id: number; name: string; registration_no?: string | null }[]>([]);

  // Create form
  const [form, setForm] = useState({ ...emptyForm });
  const [createOverrides, setCreateOverrides] = useState<OverrideMap>({});

  // Edit modal
  const [editing, setEditing] = useState<ManagedUserDetail | null>(null);
  const [editForm, setEditForm] = useState({ display_name: '', phone: '', email: '', department: '', role: '', lab_section: '', doctor_profile_id: '' });
  const [editOverrides, setEditOverrides] = useState<OverrideMap>({});

  // Confirm dialogs
  const [confirmActive, setConfirmActive] = useState<ManagedUser | null>(null);
  const [confirmReset, setConfirmReset] = useState<ManagedUser | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ManagedUser | null>(null);
  const [resetPassword, setResetPassword] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, list] = await Promise.all([api.getUserAdminMeta(), api.listUsers()]);
      setMeta(m);
      setUsers(list);
      // Prompt 15: doctor profiles for the DOCTOR login link (individual doctors only)
      api.getReferrers().then((rs) => {
        const nonDoctor = ['agent', 'clinic', 'institution', 'other', 'third party'];
        setDoctorOptions(
          (rs as any[])
            .filter((r) => !nonDoctor.includes(String(r.referrer_type || '').toLowerCase()))
            .map((r) => ({ id: Number(r.id), name: String(r.name), registration_no: r.registration_no ?? null }))
        );
      }).catch(() => setDoctorOptions([]));
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to load users', message: err.message });
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    if (hasPermission('user.manage')) load();
  }, [hasPermission, load]);

  if (!hasPermission('user.manage')) {
    return (
      <div className="bg-white border border-[#DCDAD4] rounded-2xl p-6 text-xs text-[#6D6A60]" data-testid="users-forbidden">
        You do not have permission to manage users.
      </div>
    );
  }
  if (loading || !meta) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-7 h-7 text-[#CF8852] animate-spin" />
      </div>
    );
  }

  const isLabTech = (role: string) => role === 'LAB_TECH';
  const isDoctor = (role: string) => role === 'DOCTOR';
  const doctorSelect = (id: string, value: string, onChange: (v: string) => void, disabled?: boolean) => (
    <div>
      <label className={labelCls} htmlFor={id}>Doctor profile</label>
      <select id={id} className={inputCls} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)} data-testid={id}>
        <option value="">Not linked yet</option>
        {doctorOptions.map((d) => (
          <option key={d.id} value={String(d.id)}>{d.name}{d.registration_no ? ` (Reg ${d.registration_no})` : ' (no registration no.)'}</option>
        ))}
      </select>
      <p className="text-[11px] text-[#6D6A60] mt-1">The doctor whose name and registration number are printed when this login approves its own results.</p>
    </div>
  );

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLabTech(form.role) && !form.lab_section) {
      // Prompt 10E: a technician always belongs to a lab room (also enforced by the backend)
      showToast({ type: 'warning', title: 'Lab room required', message: 'Choose the lab room for this technician.' });
      return;
    }
    setBusy(true);
    try {
      const created = await api.createUser({
        username: form.username.trim(),
        display_name: form.display_name.trim(),
        password: form.password,
        role: form.role,
        department: form.department || null,
        lab_section: isLabTech(form.role) && form.lab_section ? form.lab_section : null,
        doctor_profile_id: isDoctor(form.role) && form.doctor_profile_id ? Number(form.doctor_profile_id) : null,
        email: form.email || null,
        phone: form.phone || null,
        active: form.active,
        permission_overrides: createOverrides,
      });
      showToast({ type: 'success', title: 'User created', message: `${created.username} (${created.role}) was created.` });
      setForm({ ...emptyForm });
      setCreateOverrides({});
      setTab('list');
      await load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Create failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const openEdit = async (u: ManagedUser) => {
    try {
      const d = await api.getUser(u.id);
      setEditing(d);
      setEditForm({
        display_name: d.display_name,
        phone: d.phone || '',
        email: d.email || '',
        department: d.department || '',
        role: d.role,
        lab_section: d.lab_section || '',
        doctor_profile_id: d.doctor_profile_id ? String(d.doctor_profile_id) : '',
      });
      setEditOverrides({ ...d.permissions.overrides });
    } catch (err: any) {
      showToast({ type: 'error', title: 'Failed to open user', message: err.message });
    }
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    const isSelf = editing.id === user?.id;
    if (!isSelf && isLabTech(editForm.role) && !editForm.lab_section) {
      showToast({ type: 'warning', title: 'Lab room required', message: 'Choose the lab room for this technician.' });
      return;
    }
    setBusy(true);
    try {
      await api.updateUser(editing.id, {
        display_name: editForm.display_name,
        phone: editForm.phone || null,
        email: editForm.email || null,
        department: editForm.department || null,
        ...(!isSelf && editForm.role === editing.role && isLabTech(editing.role) ? { lab_section: editForm.lab_section || null } : {}),
        ...(editForm.role === editing.role && isDoctor(editing.role) ? { doctor_profile_id: editForm.doctor_profile_id ? Number(editForm.doctor_profile_id) : null } : {}),
      });
      if (!isSelf && editForm.role !== editing.role) {
        await api.setUserRole(editing.id, editForm.role, isLabTech(editForm.role) ? editForm.lab_section || null : null);
      }
      if (!isSelf) {
        const before = editing.permissions.overrides;
        const changes: Record<string, boolean | null> = {};
        Object.keys({ ...before, ...editOverrides }).forEach((k) => {
          const now = k in editOverrides ? editOverrides[k] : null;
          const was = k in before ? before[k] : null;
          if (now !== was) changes[k] = now;
        });
        if (Object.keys(changes).length > 0) await api.setUserPermissions(editing.id, changes);
      }
      showToast({ type: 'success', title: 'User updated', message: `${editing.username} was saved.` });
      setEditing(null);
      await load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Update failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmActive = async () => {
    if (!confirmActive) return;
    setBusy(true);
    try {
      await api.setUserActive(confirmActive.id, !confirmActive.active);
      showToast({ type: 'success', title: confirmActive.active ? 'User deactivated' : 'User reactivated', message: confirmActive.username });
      setConfirmActive(null);
      await load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Action failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmDelete = async (reason: string) => {
    if (!confirmDelete) return;
    setBusy(true);
    try {
      await api.deleteUser(confirmDelete.id, reason);
      showToast({ type: 'success', title: 'User deleted', message: `${confirmDelete.username} is hidden and cannot sign in. Restore from Catalog & Deleted.` });
      setConfirmDelete(null);
      await load();
    } catch (err: any) {
      showToast({ type: 'error', title: 'Delete failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const handleConfirmReset = async () => {
    if (!confirmReset) return;
    setBusy(true);
    try {
      await api.resetUserPassword(confirmReset.id, resetPassword);
      showToast({ type: 'success', title: 'Password reset', message: `${confirmReset.username} must use the new password.` });
      setConfirmReset(null);
      setResetPassword('');
    } catch (err: any) {
      showToast({ type: 'error', title: 'Reset failed', message: err.message });
    } finally {
      setBusy(false);
    }
  };

  const editingSelf = editing?.id === user?.id;

  return (
    <div className="space-y-5 max-w-full" data-testid="user-management-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-[#1B1B0E] flex items-center gap-2">
            <UserCog className="w-5 h-5 text-[#CF8852]" /> User Management
          </h1>
          <p className="text-xs text-[#6D6A60]">One login = one role. Add or remove permissions per user on top of the role defaults.</p>
        </div>
        <div className="flex gap-2">
          <button className={tab === 'list' ? btnPrimary : btnSecondary} onClick={() => setTab('list')} data-testid="users-tab-list">
            <UsersIcon className="w-3.5 h-3.5" /> Users
          </button>
          <button className={tab === 'create' ? btnPrimary : btnSecondary} onClick={() => setTab('create')} data-testid="users-tab-create">
            <Plus className="w-3.5 h-3.5" /> Create User
          </button>
        </div>
      </div>

      {tab === 'list' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3" data-testid="users-list">
          {users.map((u) => {
            const isSelf = u.id === user?.id;
            return (
              <div key={u.id} className={`bg-white border rounded-2xl p-4 ${u.active ? 'border-[#DCDAD4]' : 'border-[#E4E2DC] opacity-70'}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <span className="block font-bold text-sm text-[#1B1B0E] truncate">{u.display_name}</span>
                    <span className="block text-[11px] text-[#6D6A60] truncate">@{u.username}</span>
                  </div>
                  <div className="flex flex-wrap justify-end gap-1 shrink-0">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#525333] text-white">{u.role}</span>
                    {!u.active && <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#F4F3F0] text-[#6D6A60] border border-[#DCDAD4]">Inactive</span>}
                    {u.is_locked && (
                      <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-[#FDF2F0] text-[#9C2417] border border-[#F8CBC6] inline-flex items-center gap-1">
                        <Lock className="w-3 h-3" /> Locked
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-2 text-[11px] text-[#6D6A60] space-y-0.5">
                  {u.lab_section_label && <div>Section: {u.lab_section_label}</div>}
                  {u.department && <div>Department: {u.department}</div>}
                  {u.override_count > 0 && (
                    <div className="text-[#8A5608] inline-flex items-center gap-1">
                      <ShieldCheck className="w-3 h-3" /> {u.override_count} permission override(s)
                    </div>
                  )}
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className={btnSecondary} onClick={() => openEdit(u)} data-testid={`user-edit-${u.username}`}>
                    <Pencil className="w-3.5 h-3.5" /> Edit
                  </button>
                  <button className={btnSecondary} onClick={() => setConfirmReset(u)} data-testid={`user-reset-${u.username}`}>
                    <KeyRound className="w-3.5 h-3.5" /> Reset password
                  </button>
                  <button
                    className={btnSecondary}
                    onClick={() => setConfirmActive(u)}
                    disabled={isSelf}
                    title={isSelf ? 'You cannot deactivate your own account' : undefined}
                    data-testid={`user-toggle-active-${u.username}`}
                  >
                    <Power className="w-3.5 h-3.5" /> {u.active ? 'Deactivate' : 'Reactivate'}
                  </button>
                  <button
                    className={btnSecondary}
                    onClick={() => setConfirmDelete(u)}
                    disabled={isSelf}
                    title={isSelf ? 'You cannot delete your own account' : undefined}
                    data-testid={`user-delete-${u.username}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === 'create' && (
        <form onSubmit={handleCreate} className="bg-[#FAF9F6] border border-[#DCDAD4] rounded-2xl p-4 sm:p-5 space-y-4" data-testid="create-user-form">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className={labelCls} htmlFor="cu-name">Full name</label>
              <input id="cu-name" className={inputCls} required minLength={2} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-username">Username</label>
              <input id="cu-username" className={inputCls} required minLength={3} autoComplete="off" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-phone">Phone</label>
              <input id="cu-phone" className={inputCls} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-email">Email</label>
              <input id="cu-email" type="email" className={inputCls} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-dept">Department (optional)</label>
              <input id="cu-dept" className={inputCls} value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-password">Initial password (min 8 characters)</label>
              <input id="cu-password" type="password" autoComplete="new-password" className={inputCls} required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
            </div>
            <div>
              <label className={labelCls} htmlFor="cu-role">Role (one per user)</label>
              <select
                id="cu-role"
                className={inputCls}
                value={form.role}
                onChange={(e) => {
                  setForm({ ...form, role: e.target.value, lab_section: '' });
                  setCreateOverrides({});
                }}
                data-testid="create-user-role"
              >
                {meta.roles.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            {isLabTech(form.role) && (
              <div>
                <label className={labelCls} htmlFor="cu-section">Lab room *</label>
                <select id="cu-section" required aria-required="true" className={inputCls} value={form.lab_section} onChange={(e) => setForm({ ...form, lab_section: e.target.value })} data-testid="create-user-lab-section">
                  <option value="" disabled>Select a room…</option>
                  {meta.lab_sections.map((s) => (
                    <option key={s.code} value={s.code}>{s.label}</option>
                  ))}
                </select>
              </div>
            )}
            {isDoctor(form.role) && doctorSelect('create-user-doctor-profile', form.doctor_profile_id, (v) => setForm({ ...form, doctor_profile_id: v }))}
            <label className="flex items-center gap-2 text-xs text-[#54524A] sm:col-span-2">
              <input type="checkbox" className="accent-[#525333]" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
              Active (can sign in)
            </label>
          </div>
          <div>
            <span className="block text-xs font-bold text-[#1B1B0E] mb-2">Permissions</span>
            <PermissionEditor meta={meta} role={form.role} overrides={createOverrides} onChange={setCreateOverrides} />
          </div>
          <div className="flex justify-end">
            <button type="submit" className={btnPrimary} disabled={busy} data-testid="create-user-submit">
              {busy ? 'Creating…' : 'Create User'}
            </button>
          </div>
        </form>
      )}

      {/* Edit user */}
      <Modal isOpen={Boolean(editing)} onClose={() => setEditing(null)} title={editing ? `Edit ${editing.username}` : ''} subtitle={editingSelf ? 'Your own account: role, permissions and lab section are locked.' : undefined} maxWidth="2xl">
        {editing && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className={labelCls} htmlFor="eu-name">Full name</label>
                <input id="eu-name" className={inputCls} value={editForm.display_name} onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })} />
              </div>
              <div>
                <label className={labelCls} htmlFor="eu-phone">Phone</label>
                <input id="eu-phone" className={inputCls} value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
              </div>
              <div>
                <label className={labelCls} htmlFor="eu-email">Email</label>
                <input id="eu-email" className={inputCls} value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} />
              </div>
              <div>
                <label className={labelCls} htmlFor="eu-dept">Department</label>
                <input id="eu-dept" className={inputCls} value={editForm.department} onChange={(e) => setEditForm({ ...editForm, department: e.target.value })} />
              </div>
              <div>
                <label className={labelCls} htmlFor="eu-role">Role</label>
                <select
                  id="eu-role"
                  className={inputCls}
                  value={editForm.role}
                  disabled={editingSelf}
                  onChange={(e) => {
                    setEditForm({ ...editForm, role: e.target.value, lab_section: '' });
                    setEditOverrides({});
                  }}
                >
                  {meta.roles.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
              {isLabTech(editForm.role) && (
                <div>
                  <label className={labelCls} htmlFor="eu-section">Lab room *</label>
                  <select id="eu-section" required aria-required="true" className={inputCls} disabled={editingSelf} value={editForm.lab_section} onChange={(e) => setEditForm({ ...editForm, lab_section: e.target.value })}>
                    <option value="" disabled>Select a room…</option>
                    {meta.lab_sections.map((s) => (
                      <option key={s.code} value={s.code}>{s.label}</option>
                    ))}
                  </select>
                </div>
              )}
              {isDoctor(editForm.role) && editForm.role === editing.role && doctorSelect('edit-user-doctor-profile', editForm.doctor_profile_id, (v) => setEditForm({ ...editForm, doctor_profile_id: v }))}
            </div>
            <div>
              <span className="block text-xs font-bold text-[#1B1B0E] mb-2">Permissions</span>
              <PermissionEditor meta={meta} role={editForm.role} overrides={editOverrides} onChange={setEditOverrides} disabled={editingSelf} />
            </div>
            <div className="flex flex-col-reverse sm:flex-row justify-end gap-2">
              <button className={btnSecondary} onClick={() => setEditing(null)}>Cancel</button>
              <button className={btnPrimary} onClick={handleSaveEdit} disabled={busy} data-testid="edit-user-save">
                {busy ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        )}
      </Modal>

      {/* Confirm deactivate / reactivate */}
      <Modal isOpen={Boolean(confirmActive)} onClose={() => setConfirmActive(null)} title={confirmActive?.active ? 'Deactivate user?' : 'Reactivate user?'} maxWidth="sm">
        {confirmActive && (
          <div className="space-y-4 text-xs text-[#54524A]">
            <p>
              {confirmActive.active
                ? `${confirmActive.display_name} (@${confirmActive.username}) will be signed out and will not be able to sign in. Nothing is deleted.`
                : `${confirmActive.display_name} (@${confirmActive.username}) will be able to sign in again.`}
            </p>
            <div className="flex justify-end gap-2">
              <button className={btnSecondary} onClick={() => setConfirmActive(null)}>Cancel</button>
              <button className={btnPrimary} onClick={handleConfirmActive} disabled={busy} data-testid="confirm-toggle-active">
                {confirmActive.active ? 'Deactivate' : 'Reactivate'}
              </button>
            </div>
          </div>
        )}
      </Modal>

      <ConfirmDialog
        isOpen={Boolean(confirmDelete)}
        title="Delete user?"
        itemName={confirmDelete ? `${confirmDelete.display_name} (@${confirmDelete.username})` : ''}
        effect="This signs them out, blocks sign-in and removes them from new selection. Their past work and audit history are not affected."
        confirmLabel="Delete"
        requireReason
        danger
        busy={busy}
        testId="user-delete-confirm"
        onCancel={() => setConfirmDelete(null)}
        onConfirm={handleConfirmDelete}
      />

      {/* Confirm password reset */}
      <Modal isOpen={Boolean(confirmReset)} onClose={() => { setConfirmReset(null); setResetPassword(''); }} title="Reset password?" maxWidth="sm">
        {confirmReset && (
          <div className="space-y-4 text-xs text-[#54524A]">
            <p>Set a new password for {confirmReset.display_name} (@{confirmReset.username}). All of their open sessions will be signed out.</p>
            <div>
              <label className={labelCls} htmlFor="rp-new">New password (min 8 characters)</label>
              <input id="rp-new" type="password" autoComplete="new-password" className={inputCls} value={resetPassword} onChange={(e) => setResetPassword(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <button className={btnSecondary} onClick={() => { setConfirmReset(null); setResetPassword(''); }}>Cancel</button>
              <button className={btnPrimary} onClick={handleConfirmReset} disabled={busy || resetPassword.length < 8} data-testid="confirm-reset-password">
                Reset password
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
