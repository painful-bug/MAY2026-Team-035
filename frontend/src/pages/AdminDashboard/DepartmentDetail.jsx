import React, { useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import {
  ArrowLeft,
  Building2,
  CheckCircle2,
  Clock3,
  Filter,
  MapPin,
  MessageSquare,
  Search,
  Send,
  UserRound,
  Users,
  Wrench,
  X,
} from 'lucide-react';
import { useApp } from '../../store/useApp';

const STATUS_STYLES = {
  Pending: 'border-amber-100 bg-amber-50 text-amber-700',
  'In Progress': 'border-blue-100 bg-blue-50 text-blue-700',
  Resolved: 'border-emerald-100 bg-emerald-50 text-emerald-700',
};

const URGENCY_STYLES = {
  High: 'bg-rose-50 text-rose-700',
  Medium: 'bg-amber-50 text-amber-700',
  Low: 'bg-slate-100 text-slate-600',
};

const formatDateTime = (value) => {
  if (!value) return 'Not available';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
};

const getCreatedAt = (complaint) =>
  complaint.createdAt ?? `${complaint.date}T09:00:00.000Z`;

const getComplaintHistory = (complaint) => {
  if (complaint.timeline?.length) return complaint.timeline;

  const events = [
    {
      id: `${complaint.id}-raised`,
      label: 'Complaint raised',
      message: 'The resident submitted this complaint.',
      actor: complaint.raisedBy || 'Resident',
      createdAt: getCreatedAt(complaint),
    },
  ];

  if (complaint.assignee && complaint.assignee !== 'Unassigned') {
    events.push({
      id: `${complaint.id}-assigned`,
      label: 'Technician assigned',
      message: `${complaint.assignee} was assigned to this complaint.`,
      actor: 'Management',
      createdAt: complaint.updatedAt ?? getCreatedAt(complaint),
    });
  }

  if (['In Progress', 'Resolved'].includes(complaint.status)) {
    events.push({
      id: `${complaint.id}-work-started`,
      label: 'Work started',
      message: 'The assigned team started working on the issue.',
      actor: complaint.assignee || 'Management',
      createdAt: complaint.updatedAt ?? getCreatedAt(complaint),
    });
  }

  if (complaint.status === 'Resolved') {
    events.push({
      id: `${complaint.id}-resolved`,
      label: 'Marked resolved',
      message: 'Management marked the complaint as resolved.',
      actor: complaint.assignee || 'Management',
      createdAt: complaint.updatedAt ?? getCreatedAt(complaint),
    });
  }

  return events;
};

export default function DepartmentDetail() {
  const { departmentId } = useParams();
  const {
    departments,
    complaints,
    updateComplaint,
    addComplaintComment,
  } = useApp();
  const [statusFilter, setStatusFilter] = useState('All');
  const [search, setSearch] = useState('');
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);
  const [drawerTab, setDrawerTab] = useState('chat');
  const [message, setMessage] = useState('');

  const department = departments.find((item) => item.id === departmentId);
  const departmentComplaints = useMemo(
    () =>
      department
        ? complaints
            .filter((complaint) => {
              const category = complaint.category?.toLowerCase() ?? '';
              return Boolean(category) && (
                (department.categories ?? []).some(
                  (item) => item.toLowerCase() === category
                ) || department.name.toLowerCase().includes(category)
              );
            })
            .sort((first, second) =>
              (second.updatedAt ?? second.date ?? '').localeCompare(
                first.updatedAt ?? first.date ?? ''
              )
            )
        : [],
    [department, complaints]
  );

  const filteredComplaints = useMemo(() => {
    const query = search.trim().toLowerCase();
    return departmentComplaints.filter((complaint) => {
      const matchesStatus =
        statusFilter === 'All' || complaint.status === statusFilter;
      const matchesSearch =
        !query ||
        [
          complaint.title,
          complaint.description,
          complaint.flat,
          complaint.raisedBy,
          complaint.assignee,
        ].some((value) => value?.toLowerCase().includes(query));
      return matchesStatus && matchesSearch;
    });
  }, [departmentComplaints, search, statusFilter]);

  const selectedComplaint = complaints.find(
    (complaint) => complaint.id === selectedComplaintId
  );
  const activeCount = departmentComplaints.filter(
    (complaint) => complaint.status !== 'Resolved'
  ).length;
  const resolvedCount = departmentComplaints.length - activeCount;
  const unassignedCount = departmentComplaints.filter(
    (complaint) =>
      !complaint.assignee || complaint.assignee === 'Unassigned'
  ).length;

  useEffect(() => {
    if (!selectedComplaint) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape') setSelectedComplaintId(null);
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [selectedComplaint]);

  if (!department) {
    return <Navigate to="/admin/departments" replace />;
  }

  const openComplaint = (complaintId, tab = 'chat') => {
    setSelectedComplaintId(complaintId);
    setDrawerTab(tab);
    setMessage('');
  };

  const assignTechnician = (complaint, staffId) => {
    const staffMember = (department.staff ?? []).find(
      (member) => member.id === staffId
    );
    if (!staffMember) {
      updateComplaint(complaint.id, { assignee: 'Unassigned' });
      return;
    }
    updateComplaint(complaint.id, {
      assignee: `${staffMember.name} - ${staffMember.role}`,
    });
  };

  const updateStatus = (complaint, status) => {
    updateComplaint(complaint.id, {
      status,
      progress:
        status === 'Resolved'
          ? 100
          : status === 'In Progress'
            ? Math.max(Number(complaint.progress || 0), 10)
            : 0,
    });
  };

  const handleSendMessage = (event) => {
    event.preventDefault();
    if (!selectedComplaint || !message.trim()) return;
    addComplaintComment(selectedComplaint.id, message);
    setMessage('');
  };

  const getAssignedStaffId = (complaint) => {
    const assigneeName = complaint.assignee?.split(' - ')[0];
    return (
      (department.staff ?? []).find(
        (member) => member.name === assigneeName
      )?.id ?? ''
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <Link
          to="/admin/departments"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Departments
        </Link>
        <div className="mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
          <div className="flex items-start gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-indigo-50 text-indigo-600">
              <Building2 className="h-5 w-5" />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
                  {department.name}
                </h1>
                <span
                  className={`rounded-full border px-2.5 py-1 text-[9px] font-extrabold ${
                    department.status === 'Inactive'
                      ? 'border-slate-200 bg-slate-100 text-slate-500'
                      : 'border-emerald-100 bg-emerald-50 text-emerald-700'
                  }`}
                >
                  {department.status ?? 'Active'}
                </span>
              </div>
              <p className="mt-1 max-w-2xl text-xs font-semibold text-slate-400">
                {department.description || 'Department complaint workspace.'}
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(department.categories ?? []).map((category) => (
                  <span
                    key={category}
                    className="rounded-full bg-indigo-50 px-2.5 py-1 text-[9px] font-bold text-indigo-700"
                  >
                    {category}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-slate-100 bg-white px-4 py-3 text-xs shadow-sm">
            <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
              Department Manager
            </p>
            <p className="mt-1 font-extrabold text-slate-700">
              {department.head || 'Not assigned'}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="All complaints" value={departmentComplaints.length} />
        <MetricCard label="Active" value={activeCount} tone="amber" />
        <MetricCard label="Unassigned" value={unassignedCount} tone="rose" />
        <MetricCard label="Resolved" value={resolvedCount} tone="emerald" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
          <div className="space-y-3 border-b border-slate-100 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  type="search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search complaints, flats, or residents..."
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-1 rounded-xl bg-slate-50 p-1">
                <Filter className="ml-2 h-3.5 w-3.5 text-slate-400" />
                {['All', 'Pending', 'In Progress', 'Resolved'].map((status) => (
                  <button
                    type="button"
                    key={status}
                    onClick={() => setStatusFilter(status)}
                    className={`rounded-lg px-2.5 py-2 text-[9px] font-bold ${
                      statusFilter === status
                        ? 'bg-white text-indigo-600 shadow-sm'
                        : 'text-slate-500'
                    }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {filteredComplaints.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <CheckCircle2 className="mx-auto h-8 w-8 text-slate-300" />
              <p className="mt-3 text-sm font-extrabold text-slate-700">
                No complaints found
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-400">
                There are no matching complaints for this department.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredComplaints.map((complaint) => (
                <article key={complaint.id} className="p-4 hover:bg-slate-50/50">
                  <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-sm font-extrabold text-slate-800">
                          {complaint.title}
                        </h2>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${URGENCY_STYLES[complaint.urgency]}`}
                        >
                          {complaint.urgency}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs font-semibold leading-relaxed text-slate-500">
                        {complaint.description}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold text-slate-400">
                        <span className="flex items-center gap-1">
                          <MapPin className="h-3.5 w-3.5" />
                          {complaint.location || `Flat ${complaint.flat}`}
                        </span>
                        <span className="flex items-center gap-1">
                          <UserRound className="h-3.5 w-3.5" />
                          {complaint.raisedBy}
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock3 className="h-3.5 w-3.5" />
                          {formatDateTime(complaint.updatedAt ?? complaint.date)}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold ${STATUS_STYLES[complaint.status]}`}
                    >
                      {complaint.status}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 md:grid-cols-[1.2fr_0.8fr_auto]">
                    <label className="space-y-1">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Assign technician
                      </span>
                      <select
                        value={getAssignedStaffId(complaint)}
                        onChange={(event) =>
                          assignTechnician(complaint, event.target.value)
                        }
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
                      >
                        <option value="">Unassigned</option>
                        {(department.staff ?? []).map((member) => (
                          <option key={member.id} value={member.id}>
                            {member.name} · {member.role}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="space-y-1">
                      <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Status
                      </span>
                      <select
                        value={complaint.status}
                        onChange={(event) =>
                          updateStatus(complaint, event.target.value)
                        }
                        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
                      >
                        <option value="Pending">Pending</option>
                        <option value="In Progress">In Progress</option>
                        <option value="Resolved">Resolved</option>
                      </select>
                    </label>
                    <div className="flex items-end gap-2">
                      <button
                        type="button"
                        onClick={() => openComplaint(complaint.id, 'chat')}
                        className="flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-[10px] font-bold text-white hover:bg-indigo-700"
                      >
                        <MessageSquare className="h-3.5 w-3.5" />
                        Chat
                        {(complaint.comments ?? []).length > 0 && (
                          <span className="rounded-full bg-white/20 px-1.5">
                            {complaint.comments.length}
                          </span>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => openComplaint(complaint.id, 'history')}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-[10px] font-bold text-slate-600 hover:bg-slate-50"
                      >
                        History
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="h-fit space-y-4 rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
          <div>
            <h2 className="text-sm font-extrabold text-slate-800">Department team</h2>
            <p className="mt-1 text-[10px] font-semibold text-slate-400">
              Available for complaint assignment.
            </p>
          </div>
          {(department.staff ?? []).length === 0 ? (
            <p className="rounded-xl bg-slate-50 p-4 text-xs font-semibold text-slate-400">
              No technicians have been added.
            </p>
          ) : (
            <div className="space-y-2">
              {department.staff.map((member) => {
                const assignmentCount = departmentComplaints.filter(
                  (complaint) =>
                    complaint.status !== 'Resolved' &&
                    complaint.assignee?.startsWith(member.name)
                ).length;
                return (
                  <div
                    key={member.id}
                    className="rounded-xl border border-slate-100 p-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
                          <Wrench className="h-3.5 w-3.5" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-700">
                            {member.name}
                          </p>
                          <p className="text-[9px] font-semibold text-slate-400">
                            {member.role}
                          </p>
                        </div>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[9px] font-bold text-slate-500">
                        {assignmentCount} active
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div className="border-t border-slate-100 pt-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
              <Users className="h-4 w-4 text-indigo-500" />
              {department.staff?.length ?? 0} team members
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs font-semibold text-slate-500">
              <Clock3 className="h-4 w-4 text-indigo-500" />
              {department.operatingHours?.start ?? '09:00'} –{' '}
              {department.operatingHours?.end ?? '18:00'}
            </div>
          </div>
        </aside>
      </div>

      {selectedComplaint && (
        <div
          className="fixed inset-0 z-[999] bg-slate-900/50 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setSelectedComplaintId(null);
            }
          }}
        >
          <aside className="absolute inset-y-0 right-0 flex w-full max-w-2xl flex-col bg-white shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-5">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-lg font-extrabold text-slate-900">
                    {selectedComplaint.title}
                  </h2>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${STATUS_STYLES[selectedComplaint.status]}`}
                  >
                    {selectedComplaint.status}
                  </span>
                </div>
                <p className="mt-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Ticket {selectedComplaint.id} · Flat {selectedComplaint.flat}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedComplaintId(null)}
                aria-label="Close complaint"
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="border-b border-slate-100 px-6 pt-4">
              <div className="flex gap-1 rounded-xl bg-slate-50 p-1">
                <button
                  type="button"
                  onClick={() => setDrawerTab('chat')}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-xs font-bold ${
                    drawerTab === 'chat'
                      ? 'bg-white text-indigo-600 shadow-sm'
                      : 'text-slate-500'
                  }`}
                >
                  <MessageSquare className="h-4 w-4" />
                  Chat ({selectedComplaint.comments?.length ?? 0})
                </button>
                <button
                  type="button"
                  onClick={() => setDrawerTab('history')}
                  className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-xs font-bold ${
                    drawerTab === 'history'
                      ? 'bg-white text-indigo-600 shadow-sm'
                      : 'text-slate-500'
                  }`}
                >
                  <Clock3 className="h-4 w-4" />
                  History
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6">
              {drawerTab === 'chat' ? (
                <div className="space-y-3">
                  <div className="mb-5 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                    <p className="text-xs font-semibold leading-relaxed text-slate-600">
                      {selectedComplaint.description}
                    </p>
                    <p className="mt-2 text-[10px] font-bold text-slate-400">
                      Assigned to {selectedComplaint.assignee || 'Unassigned'}
                    </p>
                  </div>
                  {(selectedComplaint.comments ?? []).length === 0 ? (
                    <p className="rounded-xl bg-slate-50 p-5 text-center text-xs font-semibold text-slate-400">
                      No messages yet. Send the resident an update.
                    </p>
                  ) : (
                    selectedComplaint.comments.map((comment) => (
                      <div
                        key={comment.id}
                        className={`rounded-xl p-3 ${
                          comment.authorRole === 'Admin'
                            ? 'ml-8 bg-indigo-50'
                            : 'mr-8 bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[10px] font-extrabold text-slate-700">
                            {comment.authorName}
                            <span className="ml-1 font-semibold text-slate-400">
                              · {comment.authorRole}
                            </span>
                          </p>
                          <p className="text-[9px] font-semibold text-slate-400">
                            {formatDateTime(comment.createdAt)}
                          </p>
                        </div>
                        <p className="mt-1 text-xs font-semibold leading-relaxed text-slate-600">
                          {comment.message}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              ) : (
                <div>
                  <div className="mb-5 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <Info label="Resident" value={selectedComplaint.raisedBy} />
                      <Info label="Category" value={selectedComplaint.category} />
                      <Info
                        label="Technician"
                        value={selectedComplaint.assignee || 'Unassigned'}
                      />
                      <Info
                        label="Created"
                        value={formatDateTime(getCreatedAt(selectedComplaint))}
                      />
                    </div>
                  </div>
                  <div className="space-y-0">
                    {getComplaintHistory(selectedComplaint).map(
                      (historyEvent, index, history) => (
                        <div key={historyEvent.id} className="flex gap-3">
                          <div className="flex flex-col items-center">
                            <div
                              className={`h-3 w-3 rounded-full ${
                                index === history.length - 1
                                  ? 'bg-indigo-600'
                                  : 'bg-slate-300'
                              }`}
                            />
                            {index < history.length - 1 && (
                              <div className="h-full min-h-16 w-px bg-slate-200" />
                            )}
                          </div>
                          <div className="pb-5">
                            <p className="text-xs font-extrabold text-slate-700">
                              {historyEvent.label}
                            </p>
                            <p className="mt-1 text-[11px] font-semibold leading-relaxed text-slate-500">
                              {historyEvent.message}
                            </p>
                            <p className="mt-1 text-[9px] font-bold text-slate-400">
                              {historyEvent.actor} ·{' '}
                              {formatDateTime(historyEvent.createdAt)}
                            </p>
                          </div>
                        </div>
                      )
                    )}
                  </div>
                </div>
              )}
            </div>

            {drawerTab === 'chat' && (
              <form
                onSubmit={handleSendMessage}
                className="flex gap-2 border-t border-slate-100 bg-white p-4"
              >
                <input
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder="Send an update to the resident..."
                  className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!message.trim()}
                  className="rounded-xl bg-indigo-600 px-4 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  aria-label="Send message"
                >
                  <Send className="h-4 w-4" />
                </button>
              </form>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value, tone = 'indigo' }) {
  const tones = {
    indigo: 'text-indigo-600',
    amber: 'text-amber-600',
    rose: 'text-rose-600',
    emerald: 'text-emerald-600',
  };
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className={`mt-1 text-2xl font-extrabold ${tones[tone]}`}>{value}</p>
    </div>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 font-bold text-slate-700">{value}</p>
    </div>
  );
}
