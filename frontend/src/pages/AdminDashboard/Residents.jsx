import React, { useState } from 'react';
import { useApp } from '../../store/useApp';
import { buildInviteLink } from '../../lib/tokens';
import { Search, Edit2, Trash2, UserPlus, Plus, X, Copy, Check, Link2 } from 'lucide-react';

const emptyAddForm = { name: '', email: '', tower: 'A', flatNumber: '', phones: [''] };

export default function Residents() {
  const { users, addResident, editResident, removeResident } = useApp();
  const [searchTerm, setSearchTerm] = useState('');

  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState(emptyAddForm);
  const [invite, setInvite] = useState(null); // { token } from addResident
  const [copied, setCopied] = useState('');

  const [editUser, setEditUser] = useState(null); // user being edited
  const [editForm, setEditForm] = useState({ name: '', email: '', phone: '' });

  const residents = users.filter(
    (u) =>
      u.role === 'Resident' &&
      (u.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        u.flat.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const inviteLink = invite ? buildInviteLink(invite.token) : '';

  const copy = (field, text) => {
    navigator.clipboard?.writeText(text);
    setCopied(field);
    setTimeout(() => setCopied(''), 1500);
  };

  // --- Add Resident ---
  const setPhone = (i, val) =>
    setAddForm((f) => ({ ...f, phones: f.phones.map((p, idx) => (idx === i ? val : p)) }));
  const addPhoneRow = () => setAddForm((f) => ({ ...f, phones: [...f.phones, ''] }));
  const removePhoneRow = (i) =>
    setAddForm((f) => ({ ...f, phones: f.phones.filter((_, idx) => idx !== i) }));

  const submitAdd = (e) => {
    e.preventDefault();
    const phones = addForm.phones.map((p) => p.trim()).filter(Boolean);
    if (!addForm.name || !addForm.flatNumber || phones.length === 0) return;
    const created = addResident({ ...addForm, phones });
    setInvite(created);
    setShowAdd(false);
    setAddForm(emptyAddForm);
  };

  // --- Edit ---
  const openEdit = (u) => {
    setEditUser(u);
    setEditForm({ name: u.name, email: u.email || '', phone: u.phone || '' });
  };
  const submitEdit = (e) => {
    e.preventDefault();
    editResident(editUser.id, editForm);
    setEditUser(null);
  };

  const confirmRemove = (u) => {
    if (window.confirm(`Remove resident ${u.name} (${u.flat})? This cannot be undone.`)) {
      removeResident(u.id);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Registered Residents</h1>
          <p className="text-xs font-semibold text-slate-400 mt-1">Manage society occupants, invite new residents, and edit records.</p>
        </div>
        <button
          onClick={() => { setShowAdd(true); setInvite(null); }}
          className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all shadow-md shadow-indigo-100 self-start sm:self-auto"
        >
          <UserPlus className="w-4 h-4" /> Add Resident
        </button>
      </div>

      {/* Filter and Search */}
      <div className="bg-white p-4.5 border border-slate-100 rounded-2xl shadow-sm flex items-center justify-between gap-4">
        <div className="relative max-w-sm w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search residents by name or flat..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-2 text-xs focus:outline-none focus:border-indigo-500 focus:bg-white text-slate-700 font-semibold"
          />
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider bg-slate-100 px-3 py-1.5 border border-slate-200 rounded-lg text-slate-500 whitespace-nowrap">
          {residents.length} Occupants
        </span>
      </div>

      {/* Residents table */}
      <div className="bg-white border border-slate-100 rounded-2xl shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          {residents.length === 0 ? (
            <div className="text-center py-12 text-xs text-slate-400 font-semibold">
              No matching resident records found.
            </div>
          ) : (
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100 text-[10px] font-extrabold text-slate-400 uppercase tracking-wider">
                  <th className="px-6 py-3.5">Name</th>
                  <th className="px-6 py-3.5">Apartment Block</th>
                  <th className="px-6 py-3.5">Flat Number</th>
                  <th className="px-6 py-3.5">Mobile Phone</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                {residents.map((res) => (
                  <tr key={res.id} className="hover:bg-slate-50/20 transition-colors">
                    <td className="px-6 py-4 font-bold text-slate-800">{res.name}</td>
                    <td className="px-6 py-4">Tower {res.tower}</td>
                    <td className="px-6 py-4 font-mono text-indigo-755 font-bold">Flat {res.flat}</td>
                    <td className="px-6 py-4">{res.phone}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`text-[9px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider border ${
                          res.status === 'Active'
                            ? 'text-emerald-700 bg-emerald-50 border-emerald-100'
                            : 'text-amber-700 bg-amber-50 border-amber-100'
                        }`}
                      >
                        {res.status}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openEdit(res)}
                          className="p-1.5 border border-slate-100 hover:bg-indigo-50 hover:text-indigo-650 hover:border-indigo-100 rounded-lg text-slate-400 transition-all"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => confirmRemove(res)}
                          className="p-1.5 border border-slate-100 hover:bg-rose-50 hover:text-rose-600 hover:border-rose-100 rounded-lg text-slate-400 transition-all"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Add Resident modal */}
      {showAdd && (
        <Modal onClose={() => setShowAdd(false)} title="Add Resident">
          <form onSubmit={submitAdd} className="space-y-4">
            <Field label="Full Name">
              <input
                value={addForm.name}
                onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="John Doe"
                className={inputCls}
              />
            </Field>
            <Field label="Email Address">
              <input
                type="email"
                value={addForm.email}
                onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                placeholder="john.doe@gmail.com"
                className={inputCls}
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Tower">
                <select
                  value={addForm.tower}
                  onChange={(e) => setAddForm((f) => ({ ...f, tower: e.target.value }))}
                  className={inputCls}
                >
                  {['A', 'B', 'C', 'D'].map((t) => (
                    <option key={t} value={t}>Tower {t}</option>
                  ))}
                </select>
              </Field>
              <Field label="Flat Number">
                <input
                  value={addForm.flatNumber}
                  onChange={(e) => setAddForm((f) => ({ ...f, flatNumber: e.target.value }))}
                  placeholder="e.g. 1204"
                  className={inputCls}
                />
              </Field>
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Phone Number(s) for this flat</label>
              {addForm.phones.map((p, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={p}
                    onChange={(e) => setPhone(i, e.target.value)}
                    placeholder={`+91 9XXXX XXXXX`}
                    className={inputCls}
                  />
                  {addForm.phones.length > 1 && (
                    <button type="button" onClick={() => removePhoneRow(i)} className="p-2 text-slate-400 hover:text-rose-600">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addPhoneRow}
                className="text-[11px] font-bold text-indigo-600 hover:underline inline-flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> Add another number
              </button>
            </div>

            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-indigo-100">
              Create Invite
            </button>
          </form>
        </Modal>
      )}

      {/* Invite success modal */}
      {invite && (
        <Modal onClose={() => setInvite(null)} title="Invite created">
          <p className="text-xs font-semibold text-slate-500">
            Share this link or code with the resident. Opening the link signs them straight in;
            the code works from the login screen. It expires in 7 days and can be used once.
          </p>
          <div className="space-y-3 mt-4">
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Link2 className="w-3 h-3" /> Invite Link</label>
              <div className="flex items-center gap-2 mt-1">
                <input readOnly value={inviteLink} className={`${inputCls} font-mono text-[11px]`} />
                <CopyBtn active={copied === 'link'} onClick={() => copy('link', inviteLink)} />
              </div>
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Invite Code</label>
              <div className="flex items-center gap-2 mt-1">
                <input readOnly value={invite.token} className={`${inputCls} font-mono text-[11px]`} />
                <CopyBtn active={copied === 'code'} onClick={() => copy('code', invite.token)} />
              </div>
            </div>
          </div>
          <button onClick={() => setInvite(null)} className="w-full mt-5 bg-slate-800 hover:bg-slate-900 text-white font-bold py-3 rounded-xl transition-all">
            Done
          </button>
        </Modal>
      )}

      {/* Edit modal */}
      {editUser && (
        <Modal onClose={() => setEditUser(null)} title={`Edit ${editUser.name}`}>
          <form onSubmit={submitEdit} className="space-y-4">
            <Field label="Full Name">
              <input value={editForm.name} onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))} className={inputCls} />
            </Field>
            <Field label="Email Address">
              <input type="email" value={editForm.email} onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))} className={inputCls} />
            </Field>
            <Field label="Mobile Number">
              <input value={editForm.phone} onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))} className={inputCls} />
            </Field>
            <button type="submit" className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-indigo-100">
              Save Changes
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}

const inputCls =
  'w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-indigo-500 focus:bg-white transition-all text-slate-700 font-medium';

function Field({ label, children }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

function CopyBtn({ active, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="p-2.5 border border-slate-200 rounded-xl text-slate-500 hover:bg-indigo-50 hover:text-indigo-600 hover:border-indigo-200 transition-all flex-shrink-0"
    >
      {active ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
    </button>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm animate-fade-in" onClick={onClose}>
      <div
        className="bg-white rounded-3xl shadow-xl w-full max-w-md p-6 space-y-4 animate-slide-up max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-extrabold text-slate-900 tracking-tight">{title}</h3>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:bg-slate-100">
            <X className="w-5 h-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
