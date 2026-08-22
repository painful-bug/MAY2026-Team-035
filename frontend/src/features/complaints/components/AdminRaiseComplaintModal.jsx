import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { MapPin, Send, X } from 'lucide-react';

import { adminComplaintsApi } from '../adminComplaintsApi';
import { complaintRoutingApi } from '../routingApi';
import { departmentsApi } from '../../departments/departmentsApi';

// The admin's raise-complaint form: the resident modal's field set, plus one
// optional picker.
//
// Mirrors `pages/ResidentDashboard/Complaints.jsx` deliberately — same fields,
// same "Not sure" department default, same disabled-while-pending submit — so
// an administrator filing on a resident's behalf collects exactly what the
// resident would have. The one addition is **who it is for**, and leaving it
// empty is a real answer rather than an unfinished form: it files the complaint
// against no residential unit, which is what a complaint about the lift, the
// lobby or the clubhouse actually is.
//
// **Attachments are absent**, for the reason the resident modal gives: there is
// no upload endpoint, so collecting a photo would promise it reached somebody.
//
// **Nothing here derives the SLA, the department or the category.** The
// deadline comes from the priority in Postgres, the department from
// `resolve_complaint_department`, and the category is snapshotted from the
// chosen trade. The department picker is a *fallback* the routing rule reaches
// only when the catalogue cannot decide, which is why "Not sure" is the
// default and not a nag.

const emptyForm = {
  title: '',
  description: '',
  skillId: '',
  priority: 'medium',
  location: '',
  departmentId: '',
  forMembershipId: '',
};

const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';
const selectClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:outline-none';

function Field({ label, children }) {
  return (
    <div className="space-y-1">
      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </label>
      {children}
    </div>
  );
}

const residentLabel = (resident) => {
  const place = [resident.tower, resident.flat].filter(Boolean).join(' · ');
  const suffix = resident.role && resident.role !== 'Resident' ? ` (${resident.role})` : '';
  return `${resident.name}${suffix}${place ? ` — ${place}` : ''}`;
};

export default function AdminRaiseComplaintModal({ onClose, onCreated }) {
  const [form, setForm] = useState(emptyForm);

  const skills = useQuery({
    queryKey: ['skills'],
    queryFn: () => departmentsApi.allSkills(),
    staleTime: 5 * 60_000,
  });

  // `/department-options` rather than `/departments`: the same read the triage
  // queue draws its destination dropdown from, and the reason it exists is that
  // drawing a dropdown should not require the full admin department payload.
  const departments = useQuery({
    queryKey: ['department-options'],
    queryFn: complaintRoutingApi.departmentOptions,
    staleTime: 5 * 60_000,
  });

  const residents = useQuery({
    queryKey: ['admin-complaint-resident-options'],
    queryFn: adminComplaintsApi.residentOptions,
    staleTime: 60_000,
  });

  const skillGroups = useMemo(() => {
    const groups = {};
    for (const skill of skills.data ?? []) {
      const group = skill.category || 'Other';
      (groups[group] ||= []).push(skill);
    }
    return Object.entries(groups);
  }, [skills.data]);

  const selectedSkill = (skills.data ?? []).find((skill) => skill.id === form.skillId);

  useEffect(() => {
    const onEscape = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onEscape);
    return () => document.removeEventListener('keydown', onEscape);
  }, [onClose]);

  const create = useMutation({
    mutationFn: () =>
      adminComplaintsApi.raise({
        title: form.title.trim(),
        description: form.description.trim(),
        // The database snapshots the trade's name into `category` anyway; this
        // sends the same string so the request is well-formed either way.
        category: selectedSkill?.name || '',
        skillId: form.skillId || null,
        priority: form.priority,
        location: form.location.trim(),
        // "Not sure" is `null`, which lets the catalogue route it.
        departmentId: form.departmentId || null,
        // Empty is not a missing answer: it means the complaint belongs to no
        // residential unit and stays on the admin portal.
        forMembershipId: form.forMembershipId || null,
      }),
    onSuccess: (result) => onCreated(result),
  });

  const set = (field) => (event) =>
    setForm((current) => ({ ...current, [field]: event.target.value }));

  const canSubmit = Boolean(form.title.trim()) && Boolean(form.skillId) && !create.isPending;

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">Raise a Complaint</h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              File an issue for a resident, or one about a shared space that
              belongs to no flat.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close complaint form"
            className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <form
          className="mt-6 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!canSubmit) return;
            create.mutate();
          }}
        >
          <Field label="On behalf of resident — optional">
            <select
              value={form.forMembershipId}
              onChange={set('forMembershipId')}
              disabled={residents.isLoading}
              className={selectClass}
            >
              <option value="">
                {residents.isLoading
                  ? 'Loading residents…'
                  : 'Nobody — a community or amenity complaint'}
              </option>
              {(residents.data ?? []).map((resident) => (
                <option key={resident.membershipId} value={resident.membershipId}>
                  {residentLabel(resident)}
                </option>
              ))}
            </select>
            <p className="text-[10px] font-semibold text-slate-400">
              {residents.error
                ? 'The resident list could not be loaded. You can still file this as a community complaint.'
                : form.forMembershipId
                  ? 'The resident owns this complaint and sees it on their portal, with you recorded as the person who raised it.'
                  : 'Leave this empty for a community or amenity complaint — it stays on the admin portal and never reaches a resident’s list.'}
            </p>
          </Field>

          <Field label="Issue title">
            <input
              autoFocus
              required
              value={form.title}
              onChange={set('title')}
              placeholder="e.g. Lobby light not working"
              className={inputClass}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Trade">
              <select
                required
                disabled={skills.isLoading || skills.isError}
                value={form.skillId}
                onChange={set('skillId')}
                className={selectClass}
              >
                <option value="">
                  {skills.isLoading
                    ? 'Loading trades…'
                    : skills.isError
                      ? 'Trades unavailable'
                      : 'Choose a trade…'}
                </option>
                {skillGroups.map(([group, options]) => (
                  <optgroup key={group} label={group}>
                    {options.map((skill) => (
                      <option key={skill.id} value={skill.id}>
                        {skill.name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              {skills.isError ? (
                <p role="alert" className="text-[10px] font-semibold text-rose-600">
                  {skills.error?.message || 'Trades could not be loaded. Please try again.'}
                </p>
              ) : null}
            </Field>
            <Field label="Priority">
              {/* The stored vocabulary, not the resident form's `urgency`. The
                  SLA deadline is derived from it in Postgres. */}
              <select value={form.priority} onChange={set('priority')} className={selectClass}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
          </div>

          <Field label="Who should handle this?">
            <select
              value={form.departmentId}
              onChange={set('departmentId')}
              className={selectClass}
            >
              <option value="">Not sure</option>
              {(departments.data ?? []).map((department) => (
                <option key={department.id} value={department.id}>
                  {department.name}
                  {department.kind ? ` — ${department.kind}` : ''}
                </option>
              ))}
            </select>
            <p className="text-[10px] font-semibold text-slate-400">
              {departments.error
                ? 'The department list could not be loaded; “Not sure” still files it correctly.'
                : '“Not sure” is fine — the trade routes it, and anything it cannot route lands in triage.'}
            </p>
          </Field>

          <Field label="Exact location">
            <div className="relative">
              <MapPin className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={form.location}
                onChange={set('location')}
                placeholder="e.g. Tower B lobby, near the lift"
                className={`${inputClass} pl-10`}
              />
            </div>
          </Field>

          <Field label="Description">
            <textarea
              rows={4}
              value={form.description}
              onChange={set('description')}
              placeholder="Describe what happened and when it started…"
              className={`${inputClass} resize-none`}
            />
          </Field>

          {create.error && (
            <p role="alert" className="text-xs font-semibold text-rose-600">
              {create.error.message}
            </p>
          )}

          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!canSubmit}
              className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              <Send className="h-3.5 w-3.5" />
              {create.isPending ? 'Submitting…' : 'Submit Complaint'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
