import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../store/useApp';
import { Plus, X, ArrowLeft } from 'lucide-react';

const ROLES = ['Technician', 'Manager', 'Supervisor'];
const emptyStaff = () => ({ name: '', phone: '', role: 'Technician' });

export default function CreateDepartment() {
  const { createDepartment } = useApp();
  const navigate = useNavigate();

  const [step, setStep] = useState('form'); // 'form' | 'confirm'
  const [name, setName] = useState('');
  const [categories, setCategories] = useState(['']);
  const [staff, setStaff] = useState([emptyStaff()]);

  const setCategory = (i, val) => setCategories((c) => c.map((x, idx) => (idx === i ? val : x)));
  const addCategory = () => setCategories((c) => [...c, '']);
  const removeCategory = (i) => setCategories((c) => c.filter((_, idx) => idx !== i));

  const setStaffField = (i, field, val) =>
    setStaff((s) => s.map((m, idx) => (idx === i ? { ...m, [field]: val } : m)));
  const addStaffRow = () => setStaff((s) => [...s, emptyStaff()]);
  const removeStaffRow = (i) => setStaff((s) => s.filter((_, idx) => idx !== i));

  const cleanCategories = categories.map((c) => c.trim()).filter(Boolean);
  const cleanStaff = staff
    .map((m) => ({ ...m, name: m.name.trim(), phone: m.phone.trim() }))
    .filter((m) => m.name || m.phone);

  const canSubmit = name.trim() && cleanCategories.length > 0;

  const goToConfirm = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setStep('confirm');
  };

  const confirmCreate = () => {
    createDepartment({ name: name.trim(), categories: cleanCategories, staff: cleanStaff });
    navigate('/admin');
  };

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <button
        onClick={() => navigate('/admin')}
        className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-slate-700"
      >
        <ArrowLeft className="w-4 h-4" /> Back to Dashboard
      </button>

      {step === 'form' ? (
        <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-6 space-y-6">
          <div>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">Create New Department</h1>
            <p className="text-xs font-semibold text-slate-400 mt-1">Define a department, the complaint categories it handles, and its staff.</p>
          </div>

          <form onSubmit={goToConfirm} className="space-y-6">
            <Field label="Department Name">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Plumbing & Maintenance"
                className={inputCls}
              />
            </Field>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Complaint Categories</label>
              <p className="text-[11px] text-slate-400 font-semibold -mt-1">Specify types of issues this department handles</p>
              {categories.map((cat, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={cat}
                    onChange={(e) => setCategory(i, e.target.value)}
                    placeholder="e.g. Leaking pipes"
                    className={inputCls}
                  />
                  {categories.length > 1 && (
                    <button type="button" onClick={() => removeCategory(i)} className="p-2 text-slate-400 hover:text-rose-600">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addCategory}
                className="text-[11px] font-bold text-indigo-600 hover:underline inline-flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> Add Category
              </button>
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Staff Assignment</label>
              {staff.map((m, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input
                    value={m.name}
                    onChange={(e) => setStaffField(i, 'name', e.target.value)}
                    placeholder="Full name"
                    className={`${inputCls} flex-[1.2]`}
                  />
                  <input
                    value={m.phone}
                    onChange={(e) => setStaffField(i, 'phone', e.target.value)}
                    placeholder="Phone number"
                    className={`${inputCls} flex-1`}
                  />
                  <select
                    value={m.role}
                    onChange={(e) => setStaffField(i, 'role', e.target.value)}
                    className={`${inputCls} flex-1`}
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                  {staff.length > 1 && (
                    <button type="button" onClick={() => removeStaffRow(i)} className="p-2 text-slate-400 hover:text-rose-600">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                onClick={addStaffRow}
                className="text-[11px] font-bold text-indigo-600 hover:underline inline-flex items-center gap-1"
              >
                <Plus className="w-3.5 h-3.5" /> Add Team Member
              </button>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={() => navigate('/admin')}
                className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold py-3 rounded-xl transition-all"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!canSubmit}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-40 disabled:hover:bg-indigo-600 text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-indigo-100"
              >
                Create Department
              </button>
            </div>
          </form>
        </div>
      ) : (
        <div className="bg-white border border-slate-100 rounded-2xl shadow-sm p-6 space-y-6">
          <div>
            <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">Confirm Creation</h1>
            <p className="text-2xl font-extrabold text-slate-800 mt-2">{name.trim()}</p>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Complaint Categories</label>
            <div className="flex flex-wrap gap-2">
              {cleanCategories.map((cat, i) => (
                <span key={i} className="border border-slate-200 rounded-full px-3 py-1 text-xs font-semibold text-slate-700">
                  {cat}
                </span>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Assigned Team</label>
            {cleanStaff.length === 0 ? (
              <p className="text-xs text-slate-400 font-semibold">No staff assigned yet.</p>
            ) : (
              <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
                {cleanStaff.map((m, i) => (
                  <div key={i} className="flex items-center justify-between px-4 py-2.5 text-xs font-semibold text-slate-700">
                    <span>{m.name || '—'}</span>
                    <span className="text-slate-400">{m.phone || '—'}</span>
                    <span className="text-indigo-600 font-bold">{m.role}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              onClick={() => setStep('form')}
              className="flex-1 border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold py-3 rounded-xl transition-all"
            >
              Go Back & Edit
            </button>
            <button
              onClick={confirmCreate}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 rounded-xl transition-all shadow-md shadow-indigo-100"
            >
              Confirm Creation
            </button>
          </div>
        </div>
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
