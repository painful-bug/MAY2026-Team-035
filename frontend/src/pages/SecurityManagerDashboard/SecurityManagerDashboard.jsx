import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BadgeCheck,
  Clock3,
  Pencil,
  Plus,
  ShieldCheck,
  Trash2,
  UserCheck,
  Users,
  X,
} from 'lucide-react';
import { AUTH_ROUTES } from '../../routes/authRoutes';
import { useApp } from '../../store/useApp';
import {
  formatPhoneNumber,
  isValidMobileNumber,
  normalizePhoneNumber,
} from '../../utils/phone';

const STAFF_ROLES = ['Security Guard', 'Gate Officer', 'Supervisor'];
const SHIFTS = ['Day', 'Evening', 'Night', 'Rotating'];
const inputClass =
  'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';

const emptyMember = () => ({
  id: '',
  name: '',
  phone: '',
  role: 'Security Guard',
  shift: 'Day',
  status: 'Active',
});

function MetricCard({ icon: Icon, label, value, detail, tone = 'indigo' }) {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    slate: 'bg-slate-100 text-slate-600',
  };

  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-2 text-3xl font-extrabold text-slate-900">{value}</p>
          <p className="mt-1 text-[10px] font-semibold text-slate-400">
            {detail}
          </p>
        </div>
        <div className={`rounded-xl p-3 ${tones[tone]}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function StaffForm({ member, onChange, onClose, onSave }) {
  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <form
        onSubmit={onSave}
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">
              {member.id ? 'Edit security staff' : 'Add security staff'}
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Active staff can sign in through the Community Portal.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-slate-100 p-2 text-slate-500"
            aria-label="Close staff form"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <label className="space-y-1.5 sm:col-span-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Full name
            </span>
            <input
              required
              value={member.name}
              onChange={(event) => onChange('name', event.target.value)}
              className={inputClass}
              placeholder="Staff member name"
            />
          </label>
          <label className="space-y-1.5 sm:col-span-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Login phone number
            </span>
            <input
              required
              inputMode="numeric"
              value={member.phone}
              onChange={(event) => onChange('phone', event.target.value)}
              className={inputClass}
              placeholder="10-digit mobile number"
            />
          </label>
          <label className="space-y-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Role
            </span>
            <select
              value={member.role}
              onChange={(event) => onChange('role', event.target.value)}
              className={inputClass}
            >
              {STAFF_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Shift
            </span>
            <select
              value={member.shift}
              onChange={(event) => onChange('shift', event.target.value)}
              className={inputClass}
            >
              {SHIFTS.map((shift) => (
                <option key={shift} value={shift}>
                  {shift}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1.5 sm:col-span-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Account status
            </span>
            <select
              value={member.status}
              onChange={(event) => onChange('status', event.target.value)}
              className={inputClass}
            >
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </label>
        </div>

        <div className="mt-6 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border border-slate-200 py-3 text-xs font-bold text-slate-600"
          >
            Cancel
          </button>
          <button
            type="submit"
            className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white shadow-md shadow-indigo-100"
          >
            Save staff member
          </button>
        </div>
      </form>
    </div>
  );
}

export default function SecurityManagerDashboard({ view = 'dashboard' }) {
  const {
    currentUser,
    departments,
    visitors,
    updateDepartment,
    showToast,
  } = useApp();
  const navigate = useNavigate();
  const [editingMember, setEditingMember] = useState(null);

  const department = departments.find(
    (item) => item.id === currentUser?.departmentId
  );
  const staff = useMemo(() => department?.staff ?? [], [department]);
  const activeStaff = staff.filter(
    (member) => member.status !== 'Inactive'
  ).length;
  const today = new Date().toISOString().slice(0, 10);
  const todayEntries = visitors.filter(
    (visitor) =>
      visitor.checkedInAt?.startsWith(today) ||
      (!visitor.checkedInAt && visitor.date === today && visitor.checkInTime)
  ).length;
  const peopleInside = visitors
    .filter((visitor) => visitor.status === 'Checked In')
    .reduce((total, visitor) => total + Number(visitor.guestCount || 1), 0);

  const staffByShift = useMemo(
    () =>
      SHIFTS.map((shift) => ({
        shift,
        count: staff.filter(
          (member) =>
            (member.shift || 'Day') === shift &&
            member.status !== 'Inactive'
        ).length,
      })),
    [staff]
  );

  if (!department) {
    return (
      <div className="rounded-2xl border border-amber-100 bg-amber-50 p-6">
        <h1 className="text-lg font-extrabold text-amber-900">
          Security department unavailable
        </h1>
        <p className="mt-1 text-xs font-semibold text-amber-700">
          Ask an administrator to assign this manager account to an active
          security department.
        </p>
      </div>
    );
  }

  const saveMember = (event) => {
    event.preventDefault();
    const cleanName = editingMember.name.trim();
    const cleanPhone = normalizePhoneNumber(editingMember.phone);

    if (!cleanName || !isValidMobileNumber(cleanPhone)) {
      showToast('Enter a name and a valid 10-digit phone number.', 'error');
      return;
    }

    const duplicate = staff.some(
      (member) =>
        member.id !== editingMember.id &&
        normalizePhoneNumber(member.phone) === cleanPhone
    );
    if (duplicate) {
      showToast('That phone number already belongs to another staff member.', 'error');
      return;
    }

    const normalizedMember = {
      ...editingMember,
      name: cleanName,
      phone: cleanPhone,
    };
    const updatedStaff = editingMember.id
      ? staff.map((member) =>
          member.id === editingMember.id ? normalizedMember : member
        )
      : [...staff, normalizedMember];

    updateDepartment(department.id, { staff: updatedStaff });
    setEditingMember(null);
  };

  const removeMember = (member) => {
    if (member.id === currentUser.staffId) return;
    const confirmed = window.confirm(
      `Remove ${member.name} from the security team? Their Community Portal access will stop immediately.`
    );
    if (!confirmed) return;
    updateDepartment(department.id, {
      staff: staff.filter((item) => item.id !== member.id),
    });
  };

  const toggleStatus = (member) => {
    if (member.id === currentUser.staffId) return;
    const nextStatus = member.status === 'Inactive' ? 'Active' : 'Inactive';
    updateDepartment(department.id, {
      staff: staff.map((item) =>
        item.id === member.id ? { ...item, status: nextStatus } : item
      ),
    });
  };

  if (view === 'staff') {
    return (
      <div className="space-y-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
              Security Staff
            </h1>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Manage roles, shifts, status, and Community Portal access.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setEditingMember(emptyMember())}
            className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
          >
            <Plus className="h-4 w-4" />
            Add staff member
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {staffByShift.map(({ shift, count }) => (
            <MetricCard
              key={shift}
              icon={Clock3}
              label={`${shift} shift`}
              value={count}
              detail="Active team members"
              tone={shift === 'Night' ? 'slate' : 'indigo'}
            />
          ))}
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-5 py-4">
            <h2 className="text-sm font-extrabold text-slate-800">
              Team directory
            </h2>
          </div>
          <div className="divide-y divide-slate-100">
            {staff.map((member) => {
              const isCurrentManager = member.id === currentUser.staffId;
              return (
                <article
                  key={member.id}
                  className="flex flex-col justify-between gap-4 px-5 py-4 lg:flex-row lg:items-center"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                      {member.role === 'Manager' ? (
                        <BadgeCheck className="h-5 w-5" />
                      ) : (
                        <ShieldCheck className="h-5 w-5" />
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-extrabold text-slate-800">
                          {member.name}
                        </p>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${
                            member.status === 'Inactive'
                              ? 'bg-slate-100 text-slate-500'
                              : 'bg-emerald-50 text-emerald-700'
                          }`}
                        >
                          {member.status || 'Active'}
                        </span>
                        {isCurrentManager && (
                          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[9px] font-bold text-indigo-700">
                            Your account
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-[10px] font-semibold text-slate-400">
                        {member.role} · {member.shift || 'Day'} shift ·{' '}
                        {formatPhoneNumber(member.phone)}
                      </p>
                    </div>
                  </div>
                  {!isCurrentManager && (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => toggleStatus(member)}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                      >
                        {member.status === 'Inactive' ? 'Activate' : 'Deactivate'}
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setEditingMember({
                            ...member,
                            shift: member.shift || 'Day',
                            status: member.status || 'Active',
                          })
                        }
                        className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-indigo-50 hover:text-indigo-600"
                        aria-label={`Edit ${member.name}`}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => removeMember(member)}
                        className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-rose-50 hover:text-rose-600"
                        aria-label={`Remove ${member.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        </section>

        {editingMember && (
          <StaffForm
            member={editingMember}
            onChange={(field, value) =>
              setEditingMember((current) => ({ ...current, [field]: value }))
            }
            onClose={() => setEditingMember(null)}
            onSave={saveMember}
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Security Operations
          </h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Welcome, {currentUser.name}. Manage your team and monitor gate
            activity.
          </p>
        </div>
        <button
          type="button"
          onClick={() =>
            navigate(`${AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD}/staff`)
          }
          className="flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100"
        >
          <Users className="h-4 w-4" />
          Manage Staff
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Users}
          label="Active Staff"
          value={activeStaff}
          detail={`${staff.length} total team members`}
        />
        <MetricCard
          icon={UserCheck}
          label="Currently Inside"
          value={peopleInside}
          detail="Visitors across the community"
          tone="emerald"
        />
        <MetricCard
          icon={ShieldCheck}
          label="Today's Entries"
          value={todayEntries}
          detail="Recorded at society gates"
          tone="amber"
        />
        <MetricCard
          icon={Clock3}
          label="Operating Hours"
          value={`${department.operatingHours?.start ?? '00:00'}–${department.operatingHours?.end ?? '23:59'}`}
          detail="Security department coverage"
          tone="slate"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-extrabold text-slate-900">
                Team availability
              </h2>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                Active staffing by shift.
              </p>
            </div>
            <button
              type="button"
              onClick={() =>
                navigate(`${AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD}/staff`)
              }
              className="text-xs font-bold text-indigo-600"
            >
              View team
            </button>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {staffByShift.map(({ shift, count }) => (
              <div key={shift} className="rounded-xl bg-slate-50 p-4">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {shift}
                </p>
                <p className="mt-2 text-2xl font-extrabold text-slate-800">
                  {count}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm">
          <h2 className="text-base font-extrabold text-slate-900">
            Quick operations
          </h2>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Open common security workspaces.
          </p>
          <div className="mt-5 space-y-2">
            {[
              ['Visitor access', 'visitors'],
              ['Gate history', 'history'],
              ['Emergency desk', 'emergency'],
            ].map(([label, path]) => (
              <button
                type="button"
                key={path}
                onClick={() =>
                  navigate(
                    `${AUTH_ROUTES.SECURITY_MANAGER_DASHBOARD}/${path}`
                  )
                }
                className="flex w-full items-center justify-between rounded-xl border border-slate-100 px-4 py-3 text-left text-xs font-bold text-slate-600 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700"
              >
                {label}
                <span>→</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
