import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  BriefcaseBusiness,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Eye,
  Mail,
  Pencil,
  Phone,
  Plus,
  Search,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-react';
import { useApp } from '../../store/useApp';

const CATEGORY_OPTIONS = [
  'Plumbing',
  'Electrical',
  'Infrastructure',
  'Cleaning',
  'Security',
  'Others',
];

const STAFF_ROLES = ['Technician', 'Supervisor', 'Manager', 'Coordinator'];

const emptyStaffMember = () => ({
  id: '',
  name: '',
  phone: '',
  role: 'Technician',
});

const emptyDepartment = () => ({
  name: '',
  description: '',
  categories: [],
  head: '',
  email: '',
  phone: '',
  operatingHours: { start: '09:00', end: '18:00' },
  slaHours: 24,
  status: 'Active',
  staff: [emptyStaffMember()],
});

const getDepartmentForm = (department) => ({
  ...emptyDepartment(),
  ...department,
  categories: [...(department.categories ?? [])],
  operatingHours: {
    start: department.operatingHours?.start ?? '09:00',
    end: department.operatingHours?.end ?? '18:00',
  },
  staff: department.staff?.length
    ? department.staff.map((member) => ({ ...member }))
    : [emptyStaffMember()],
});

const getDepartmentComplaints = (department, complaints) =>
  complaints.filter((complaint) => {
    const category = complaint.category?.toLowerCase() ?? '';
    return Boolean(category) && (
      (department.categories ?? []).some(
        (item) => item.toLowerCase() === category
      ) || department.name.toLowerCase().includes(category)
    );
  });

export default function Departments() {
  const {
    departments,
    complaints,
    createDepartment,
    updateDepartment,
    setDepartmentStatus,
    deleteDepartment,
  } = useApp();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [modalMode, setModalMode] = useState(null);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState(null);
  const [deleteDepartmentId, setDeleteDepartmentId] = useState(null);
  const [form, setForm] = useState(emptyDepartment);

  const selectedDepartment = departments.find(
    (department) => department.id === selectedDepartmentId
  );
  const departmentToDelete = departments.find(
    (department) => department.id === deleteDepartmentId
  );

  useEffect(() => {
    if (searchParams.get('create') !== '1') return;
    setForm(emptyDepartment());
    setSelectedDepartmentId(null);
    setModalMode('create');
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!modalMode && !deleteDepartmentId) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setModalMode(null);
        setDeleteDepartmentId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [modalMode, deleteDepartmentId]);

  const departmentSummaries = useMemo(
    () =>
      departments.map((department) => {
        const ownedComplaints = getDepartmentComplaints(department, complaints);
        const activeComplaints = ownedComplaints.filter(
          (complaint) => complaint.status !== 'Resolved'
        );
        const overdueComplaints = activeComplaints.filter(
          (complaint) =>
            complaint.expectedResolutionAt &&
            new Date(complaint.expectedResolutionAt).getTime() < Date.now()
        );
        return {
          ...department,
          status: department.status ?? 'Active',
          activeComplaintCount: activeComplaints.length,
          resolvedComplaintCount: ownedComplaints.length - activeComplaints.length,
          overdueComplaintCount: overdueComplaints.length,
        };
      }),
    [departments, complaints]
  );

  const filteredDepartments = useMemo(() => {
    const query = search.trim().toLowerCase();
    return departmentSummaries.filter((department) => {
      const matchesStatus =
        statusFilter === 'All' || department.status === statusFilter;
      const matchesSearch =
        !query ||
        [
          department.name,
          department.description,
          department.head,
          department.email,
          ...(department.categories ?? []),
          ...(department.staff ?? []).map((member) => member.name),
        ].some((value) => value?.toLowerCase().includes(query));
      return matchesStatus && matchesSearch;
    });
  }, [departmentSummaries, search, statusFilter]);

  const activeDepartmentCount = departments.filter(
    (department) => department.status !== 'Inactive'
  ).length;
  const totalStaffCount = departments.reduce(
    (total, department) => total + (department.staff?.length ?? 0),
    0
  );
  const activeComplaintCount = complaints.filter(
    (complaint) => complaint.status !== 'Resolved'
  ).length;

  const openCreate = () => {
    setSelectedDepartmentId(null);
    setForm(emptyDepartment());
    setModalMode('create');
  };

  const openView = (department) => {
    navigate(`/admin/departments/${department.id}`);
  };

  const openEdit = (department) => {
    setSelectedDepartmentId(department.id);
    setForm(getDepartmentForm(department));
    setModalMode('edit');
  };

  const closeModal = () => {
    setModalMode(null);
    setSelectedDepartmentId(null);
  };

  const toggleCategory = (category) => {
    setForm((current) => ({
      ...current,
      categories: current.categories.includes(category)
        ? current.categories.filter((item) => item !== category)
        : [...current.categories, category],
    }));
  };

  const setStaffField = (index, field, value) => {
    setForm((current) => ({
      ...current,
      staff: current.staff.map((member, memberIndex) =>
        memberIndex === index ? { ...member, [field]: value } : member
      ),
    }));
  };

  const removeStaffMember = (index) => {
    setForm((current) => ({
      ...current,
      staff:
        current.staff.length === 1
          ? [emptyStaffMember()]
          : current.staff.filter((_, memberIndex) => memberIndex !== index),
    }));
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!form.name.trim() || form.categories.length === 0) return;

    const departmentData = {
      ...form,
      staff: form.staff.filter((member) => member.name.trim()),
    };
    const result =
      modalMode === 'edit' && selectedDepartmentId
        ? updateDepartment(selectedDepartmentId, departmentData)
        : createDepartment(departmentData);
    if (result) closeModal();
  };

  const selectedSummary = departmentSummaries.find(
    (department) => department.id === selectedDepartmentId
  );
  const selectedComplaints = selectedDepartment
    ? getDepartmentComplaints(selectedDepartment, complaints)
    : [];
  const deleteActiveComplaintCount = departmentToDelete
    ? getDepartmentComplaints(departmentToDelete, complaints).filter(
        (complaint) => complaint.status !== 'Resolved'
      ).length
    : 0;

  const confirmDelete = () => {
    if (!deleteDepartmentId) return;
    const result = deleteDepartment(deleteDepartmentId);
    if (result?.ok) setDeleteDepartmentId(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            Departments
          </h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Manage service teams, complaint ownership, staffing, and response targets.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreate}
          className="flex items-center justify-center gap-1.5 self-start rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          New Department
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <SummaryCard
          label="Departments"
          value={departments.length}
          helper={`${activeDepartmentCount} active`}
          icon={Building2}
          tone="indigo"
        />
        <SummaryCard
          label="Team Members"
          value={totalStaffCount}
          helper="Across all departments"
          icon={Users}
          tone="emerald"
        />
        <SummaryCard
          label="Open Complaints"
          value={activeComplaintCount}
          helper="Live department workload"
          icon={BriefcaseBusiness}
          tone="amber"
        />
        <SummaryCard
          label="Unassigned Types"
          value={
            CATEGORY_OPTIONS.filter(
              (category) =>
                !departments.some((department) =>
                  department.categories?.includes(category)
                )
            ).length
          }
          helper="Categories without an owner"
          icon={AlertTriangle}
          tone="rose"
        />
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-slate-100 bg-white p-4 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search departments, categories, or staff..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
        <div className="flex rounded-xl bg-slate-50 p-1">
          {['All', 'Active', 'Inactive'].map((status) => (
            <button
              type="button"
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg px-3 py-2 text-[10px] font-bold transition-colors ${
                statusFilter === status
                  ? 'bg-white text-indigo-600 shadow-sm'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {filteredDepartments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-16 text-center">
          <Building2 className="mx-auto h-9 w-9 text-slate-300" />
          <h2 className="mt-3 text-sm font-extrabold text-slate-700">
            {departments.length === 0
              ? 'Create your first department'
              : 'No matching departments'}
          </h2>
          <p className="mx-auto mt-1 max-w-sm text-xs font-semibold text-slate-400">
            {departments.length === 0
              ? 'Set complaint ownership, add team members, and define response targets.'
              : 'Try changing the search or status filter.'}
          </p>
          {departments.length === 0 && (
            <button
              type="button"
              onClick={openCreate}
              className="mt-4 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-indigo-700"
            >
              Create Department
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {filteredDepartments.map((department) => (
            <article
              key={department.id}
              className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm transition-all hover:border-indigo-100 hover:shadow-md"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="truncate text-sm font-extrabold text-slate-800">
                        {department.name}
                      </h2>
                      <StatusBadge status={department.status ?? 'Active'} />
                    </div>
                    <p className="mt-1 line-clamp-2 text-[11px] font-semibold leading-relaxed text-slate-400">
                      {department.description || 'No description added.'}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => openView(department)}
                  className="flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-2 text-[10px] font-bold text-slate-500 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-600"
                  aria-label={`View ${department.name}`}
                >
                  <Eye className="h-4 w-4" />
                  Open
                </button>
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {(department.categories ?? []).map((category) => (
                  <span
                    key={category}
                    className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-[9px] font-bold text-indigo-700"
                  >
                    {category}
                  </span>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-slate-50 p-3 text-[10px] font-semibold text-slate-500 sm:grid-cols-4">
                <Metric label="Staff" value={department.staff?.length ?? 0} />
                <Metric label="Open tickets" value={department.activeComplaintCount} />
                <Metric label="Overdue" value={department.overdueComplaintCount} />
                <Metric label="SLA" value={`${department.slaHours ?? 24}h`} />
              </div>

              <div className="mt-4 flex flex-col justify-between gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center">
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                    Department Head
                  </p>
                  <p className="mt-0.5 text-xs font-bold text-slate-700">
                    {department.head || 'Not assigned'}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      setDepartmentStatus(
                        department.id,
                        department.status === 'Inactive' ? 'Active' : 'Inactive'
                      )
                    }
                    className="rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                  >
                    {department.status === 'Inactive' ? 'Activate' : 'Deactivate'}
                  </button>
                  <button
                    type="button"
                    onClick={() => openEdit(department)}
                    className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-indigo-200 hover:text-indigo-600"
                    aria-label={`Edit ${department.name}`}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setDeleteDepartmentId(department.id)}
                    className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                    aria-label={`Delete ${department.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      {modalMode && (
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeModal();
          }}
        >
          <div className="max-h-[92vh] w-full max-w-3xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  {modalMode === 'create'
                    ? 'Create Department'
                    : modalMode === 'edit'
                      ? 'Edit Department'
                      : selectedDepartment?.name}
                </h2>
                <p className="mt-1 text-xs font-semibold text-slate-400">
                  {modalMode === 'view'
                    ? 'Team details, service ownership, and current workload.'
                    : 'Configure ownership, contacts, staffing, and response targets.'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeModal}
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
                aria-label="Close department dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {modalMode === 'view' && selectedDepartment ? (
              <DepartmentDetails
                department={selectedDepartment}
                summary={selectedSummary}
                complaints={selectedComplaints}
                onEdit={() => openEdit(selectedDepartment)}
              />
            ) : (
              <DepartmentForm
                form={form}
                setForm={setForm}
                toggleCategory={toggleCategory}
                setStaffField={setStaffField}
                removeStaffMember={removeStaffMember}
                onAddStaff={() =>
                  setForm((current) => ({
                    ...current,
                    staff: [...current.staff, emptyStaffMember()],
                  }))
                }
                onCancel={closeModal}
                onSubmit={handleSubmit}
                isEditing={modalMode === 'edit'}
              />
            )}
          </div>
        </div>
      )}

      {departmentToDelete && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-rose-50 text-rose-600">
              <Trash2 className="h-5 w-5" />
            </div>
            <h2 className="mt-4 text-lg font-extrabold text-slate-900">
              Delete {departmentToDelete.name}?
            </h2>
            {deleteActiveComplaintCount > 0 ? (
              <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
                This department owns {deleteActiveComplaintCount} active complaint
                {deleteActiveComplaintCount === 1 ? '' : 's'}. Resolve or reassign
                them before deletion. You can deactivate the department now instead.
              </p>
            ) : (
              <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
                This permanently removes its configuration and staff directory.
                Complaint records will remain available.
              </p>
            )}
            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setDeleteDepartmentId(null)}
                className="flex-1 rounded-xl border border-slate-200 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
              >
                Cancel
              </button>
              {deleteActiveComplaintCount > 0 ? (
                <button
                  type="button"
                  onClick={() => {
                    setDepartmentStatus(departmentToDelete.id, 'Inactive');
                    setDeleteDepartmentId(null);
                  }}
                  className="flex-1 rounded-xl bg-slate-800 py-2.5 text-xs font-bold text-white hover:bg-slate-900"
                >
                  Deactivate
                </button>
              ) : (
                <button
                  type="button"
                  onClick={confirmDelete}
                  className="flex-1 rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white hover:bg-rose-700"
                >
                  Delete Department
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, helper, icon: Icon, tone }) {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-600',
    rose: 'bg-rose-50 text-rose-600',
  };
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
            {label}
          </p>
          <p className="mt-1 text-2xl font-extrabold text-slate-800">{value}</p>
          <p className="mt-1 text-[10px] font-semibold text-slate-400">{helper}</p>
        </div>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${tones[tone]}`}>
          <Icon className="h-4 w-4" />
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-extrabold text-slate-700">{value}</p>
    </div>
  );
}

function StatusBadge({ status }) {
  const isActive = status !== 'Inactive';
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[9px] font-extrabold ${
        isActive
          ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
          : 'border-slate-200 bg-slate-100 text-slate-500'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

function DepartmentForm({
  form,
  setForm,
  toggleCategory,
  setStaffField,
  removeStaffMember,
  onAddStaff,
  onCancel,
  onSubmit,
  isEditing,
}) {
  const inputClass =
    'w-full rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none';
  return (
    <form onSubmit={onSubmit} className="mt-6 space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Department name" required>
          <input
            required
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            placeholder="e.g. Electrical Services"
            className={inputClass}
          />
        </Field>
        <Field label="Status">
          <select
            value={form.status}
            onChange={(event) =>
              setForm((current) => ({ ...current, status: event.target.value }))
            }
            className={inputClass}
          >
            <option value="Active">Active</option>
            <option value="Inactive">Inactive</option>
          </select>
        </Field>
      </div>

      <Field label="Description">
        <textarea
          rows={2}
          value={form.description}
          onChange={(event) =>
            setForm((current) => ({
              ...current,
              description: event.target.value,
            }))
          }
          placeholder="What does this department handle?"
          className={`${inputClass} resize-none`}
        />
      </Field>

      <Field label="Complaint categories" required>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {CATEGORY_OPTIONS.map((category) => (
            <label
              key={category}
              className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2.5 text-[10px] font-bold transition-colors ${
                form.categories.includes(category)
                  ? 'border-indigo-200 bg-indigo-50 text-indigo-700'
                  : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300'
              }`}
            >
              <input
                type="checkbox"
                checked={form.categories.includes(category)}
                onChange={() => toggleCategory(category)}
                className="accent-indigo-600"
              />
              {category}
            </label>
          ))}
        </div>
        {form.categories.length === 0 && (
          <p className="mt-1 text-[10px] font-semibold text-rose-500">
            Select at least one complaint category.
          </p>
        )}
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Department head">
          <input
            value={form.head}
            onChange={(event) =>
              setForm((current) => ({ ...current, head: event.target.value }))
            }
            placeholder="Full name"
            className={inputClass}
          />
        </Field>
        <Field label="Contact email">
          <input
            type="email"
            value={form.email}
            onChange={(event) =>
              setForm((current) => ({ ...current, email: event.target.value }))
            }
            placeholder="department@example.com"
            className={inputClass}
          />
        </Field>
        <Field label="Contact phone">
          <input
            value={form.phone}
            onChange={(event) =>
              setForm((current) => ({ ...current, phone: event.target.value }))
            }
            placeholder="+91 98765 43210"
            className={inputClass}
          />
        </Field>
        <Field label="Response SLA (hours)">
          <input
            type="number"
            min="1"
            max="720"
            required
            value={form.slaHours}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                slaHours: Number(event.target.value),
              }))
            }
            className={inputClass}
          />
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Opening time">
          <input
            type="time"
            value={form.operatingHours.start}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                operatingHours: {
                  ...current.operatingHours,
                  start: event.target.value,
                },
              }))
            }
            className={inputClass}
          />
        </Field>
        <Field label="Closing time">
          <input
            type="time"
            value={form.operatingHours.end}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                operatingHours: {
                  ...current.operatingHours,
                  end: event.target.value,
                },
              }))
            }
            className={inputClass}
          />
        </Field>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-100 bg-slate-50 p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-extrabold text-slate-700">Team members</p>
            <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
              Add staff who can be assigned to complaints.
            </p>
          </div>
          <button
            type="button"
            onClick={onAddStaff}
            className="flex items-center gap-1 rounded-lg bg-white px-3 py-2 text-[10px] font-bold text-indigo-600 shadow-sm"
          >
            <Plus className="h-3.5 w-3.5" /> Add member
          </button>
        </div>
        {form.staff.map((member, index) => (
          <div
            key={member.id || `new-staff-${index}`}
            className="grid gap-2 rounded-xl border border-slate-100 bg-white p-3 sm:grid-cols-[1.2fr_1fr_1fr_auto]"
          >
            <input
              value={member.name}
              onChange={(event) =>
                setStaffField(index, 'name', event.target.value)
              }
              placeholder="Full name"
              className={inputClass}
            />
            <input
              value={member.phone}
              onChange={(event) =>
                setStaffField(index, 'phone', event.target.value)
              }
              placeholder="Phone"
              className={inputClass}
            />
            <select
              value={member.role}
              onChange={(event) =>
                setStaffField(index, 'role', event.target.value)
              }
              className={inputClass}
            >
              {STAFF_ROLES.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => removeStaffMember(index)}
              className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
              aria-label="Remove team member"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="flex gap-3 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="flex-1 rounded-xl border border-slate-200 py-3 text-xs font-bold text-slate-600 hover:bg-slate-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={!form.name.trim() || form.categories.length === 0}
          className="flex-1 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {isEditing ? 'Save Changes' : 'Create Department'}
        </button>
      </div>
    </form>
  );
}

function DepartmentDetails({ department, summary, complaints, onEdit }) {
  return (
    <div className="mt-6 space-y-5">
      <div className="grid gap-3 sm:grid-cols-4">
        <MetricPanel
          label="Status"
          value={department.status ?? 'Active'}
          icon={CheckCircle2}
        />
        <MetricPanel
          label="Team size"
          value={department.staff?.length ?? 0}
          icon={Users}
        />
        <MetricPanel
          label="Open tickets"
          value={summary?.activeComplaintCount ?? 0}
          icon={BriefcaseBusiness}
        />
        <MetricPanel
          label="Response SLA"
          value={`${department.slaHours ?? 24} hours`}
          icon={Clock3}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-100 p-4">
          <h3 className="text-xs font-extrabold text-slate-700">Department details</h3>
          <p className="mt-2 text-xs font-semibold leading-relaxed text-slate-500">
            {department.description || 'No description added.'}
          </p>
          <div className="mt-4 space-y-2.5 text-xs font-semibold text-slate-500">
            <DetailRow icon={UserRound} value={department.head || 'No department head'} />
            <DetailRow icon={Mail} value={department.email || 'No email added'} />
            <DetailRow icon={Phone} value={department.phone || 'No phone added'} />
            <DetailRow
              icon={Clock3}
              value={`${department.operatingHours?.start ?? '09:00'} – ${department.operatingHours?.end ?? '18:00'}`}
            />
          </div>
        </div>
        <div className="rounded-2xl border border-slate-100 p-4">
          <h3 className="text-xs font-extrabold text-slate-700">Complaint ownership</h3>
          <div className="mt-3 flex flex-wrap gap-2">
            {(department.categories ?? []).map((category) => (
              <span
                key={category}
                className="rounded-full bg-indigo-50 px-2.5 py-1 text-[10px] font-bold text-indigo-700"
              >
                {category}
              </span>
            ))}
          </div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="Open" value={summary?.activeComplaintCount ?? 0} />
            <Metric label="Resolved" value={summary?.resolvedComplaintCount ?? 0} />
            <Metric label="Overdue" value={summary?.overdueComplaintCount ?? 0} />
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-100">
        <div className="border-b border-slate-100 px-4 py-3">
          <h3 className="text-xs font-extrabold text-slate-700">Staff directory</h3>
        </div>
        {department.staff?.length ? (
          <div className="divide-y divide-slate-100">
            {department.staff.map((member) => (
              <div
                key={member.id}
                className="flex flex-col justify-between gap-2 px-4 py-3 text-xs sm:flex-row sm:items-center"
              >
                <div>
                  <p className="font-bold text-slate-700">{member.name}</p>
                  <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                    {member.role}
                  </p>
                </div>
                <p className="font-semibold text-slate-500">
                  {member.phone || 'No phone'}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            No staff assigned.
          </p>
        )}
      </div>

      <div className="rounded-2xl border border-slate-100">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h3 className="text-xs font-extrabold text-slate-700">Recent complaints</h3>
          <span className="text-[10px] font-bold text-slate-400">
            {complaints.length} total
          </span>
        </div>
        {complaints.length ? (
          <div className="divide-y divide-slate-100">
            {complaints.slice(0, 4).map((complaint) => (
              <div
                key={complaint.id}
                className="flex items-center justify-between gap-3 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-slate-700">
                    {complaint.title}
                  </p>
                  <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                    Flat {complaint.flat} · {complaint.urgency} urgency
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-slate-500">
                    {complaint.status}
                  </span>
                  <ChevronRight className="h-3.5 w-3.5 text-slate-300" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-6 text-center text-xs font-semibold text-slate-400">
            No complaints in this department’s categories.
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={onEdit}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 py-3 text-xs font-bold text-white hover:bg-indigo-700"
      >
        <Pencil className="h-4 w-4" /> Edit Department
      </button>
    </div>
  );
}

function MetricPanel({ label, value, icon: Icon }) {
  return (
    <div className="rounded-xl bg-slate-50 p-3">
      <Icon className="h-4 w-4 text-indigo-600" />
      <p className="mt-2 text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-xs font-extrabold text-slate-700">{value}</p>
    </div>
  );
}

function DetailRow({ icon: Icon, value }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      <span>{value}</span>
    </div>
  );
}

function Field({ label, required = false, children }) {
  return (
    <div className="space-y-1.5">
      <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
        {label}
        {required && <span className="text-rose-500"> *</span>}
      </label>
      {children}
    </div>
  );
}
