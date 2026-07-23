import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  CalendarClock,
  Camera,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock3,
  Filter,
  HelpCircle,
  MapPin,
  MessageSquare,
  Paperclip,
  Plus,
  RotateCcw,
  Search,
  Send,
  Star,
  UserRound,
  Wrench,
  X,
} from 'lucide-react';
import { useApp } from '../../store/useApp';
import { residentFaqs } from '../../data/residentFaqs';

const CATEGORIES = [
  'Plumbing',
  'Electrical',
  'Infrastructure',
  'Cleaning',
  'Security',
  'Others',
];

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

const COMPLAINT_FAQS = residentFaqs.filter(
  (faq) => faq.category === 'Complaints'
);

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

const getExpectedResolutionAt = (complaint) => {
  if (complaint.expectedResolutionAt) {
    return complaint.expectedResolutionAt;
  }

  const expectedAt = new Date(getCreatedAt(complaint));
  const hours = { High: 24, Medium: 48, Low: 72 }[complaint.urgency] ?? 48;
  expectedAt.setHours(expectedAt.getHours() + hours);
  return expectedAt.toISOString();
};

const getComplaintTimeline = (complaint) => {
  if (complaint.timeline?.length) {
    return complaint.timeline;
  }

  const createdAt = getCreatedAt(complaint);
  const events = [
    {
      id: `${complaint.id}-raised`,
      type: 'raised',
      label: 'Complaint raised',
      message: 'Complaint submitted to the management team.',
      actor: complaint.raisedBy,
      createdAt,
    },
  ];

  if (complaint.assignee && complaint.assignee !== 'Unassigned') {
    events.push({
      id: `${complaint.id}-assigned`,
      type: 'assigned',
      label: 'Technician assigned',
      message: `${complaint.assignee} was assigned to this complaint.`,
      actor: 'Management',
      createdAt,
    });
  }

  if (complaint.status === 'In Progress' || complaint.status === 'Resolved') {
    events.push({
      id: `${complaint.id}-progress`,
      type: 'in-progress',
      label: 'Work started',
      message: 'The assigned team started working on the issue.',
      actor: complaint.assignee || 'Management',
      createdAt,
    });
  }

  if (complaint.status === 'Resolved') {
    events.push({
      id: `${complaint.id}-resolved`,
      type: 'resolved',
      label: 'Marked resolved',
      message: 'Management marked the complaint as resolved.',
      actor: complaint.assignee || 'Management',
      createdAt,
    });
  }

  return events;
};

const getLatestUpdate = (complaint) => {
  const updates = [
    ...getComplaintTimeline(complaint),
    ...(complaint.comments ?? []),
  ].sort((first, second) =>
    (second.createdAt ?? '').localeCompare(first.createdAt ?? '')
  );
  return updates[0]?.createdAt ?? complaint.updatedAt ?? getCreatedAt(complaint);
};

const readAttachment = (file) =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () =>
      resolve({
        id: `${file.name}-${file.lastModified}`,
        name: file.name,
        type: file.type,
        size: file.size,
        dataUrl: reader.result,
      });
    reader.onerror = () => reject(new Error('Unable to read the selected file.'));
    reader.readAsDataURL(file);
  });

export default function Complaints() {
  const {
    complaints,
    currentUser,
    raiseComplaint,
    addComplaintComment,
    reopenComplaint,
    confirmComplaintResolution,
    markComplaintRead,
  } = useApp();
  const [isRaiseModalOpen, setIsRaiseModalOpen] = useState(false);
  const [selectedComplaintId, setSelectedComplaintId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('All');
  const [categoryFilter, setCategoryFilter] = useState('All');
  const [urgencyFilter, setUrgencyFilter] = useState('All');
  const [searchTerm, setSearchTerm] = useState('');
  const [form, setForm] = useState({
    title: '',
    description: '',
    category: 'Plumbing',
    urgency: 'Medium',
    location: '',
    attachments: [],
  });
  const [attachmentError, setAttachmentError] = useState('');
  const [comment, setComment] = useState('');
  const [rating, setRating] = useState(0);
  const [feedback, setFeedback] = useState('');
  const [isReopening, setIsReopening] = useState(false);
  const [reopenReason, setReopenReason] = useState('');
  const [openFaqId, setOpenFaqId] = useState(COMPLAINT_FAQS[0]?.id ?? null);

  const userComplaints = useMemo(
    () =>
      complaints.filter(
        (complaint) => complaint.userId === currentUser?.id
      ),
    [complaints, currentUser?.id]
  );
  const selectedComplaint = userComplaints.find(
    (complaint) => complaint.id === selectedComplaintId
  );

  const filteredComplaints = useMemo(() => {
    const query = searchTerm.trim().toLowerCase();
    return userComplaints.filter((complaint) => {
      const matchesStatus =
        statusFilter === 'All' ||
        (statusFilter === 'Active'
          ? complaint.status !== 'Resolved'
          : complaint.status === 'Resolved');
      const matchesCategory =
        categoryFilter === 'All' || complaint.category === categoryFilter;
      const matchesUrgency =
        urgencyFilter === 'All' || complaint.urgency === urgencyFilter;
      const matchesSearch =
        !query ||
        [
          complaint.title,
          complaint.description,
          complaint.location,
          complaint.assignee,
          complaint.id,
        ].some((value) => value?.toLowerCase().includes(query));
      return (
        matchesStatus &&
        matchesCategory &&
        matchesUrgency &&
        matchesSearch
      );
    });
  }, [
    userComplaints,
    statusFilter,
    categoryFilter,
    urgencyFilter,
    searchTerm,
  ]);

  useEffect(() => {
    if (!isRaiseModalOpen && !selectedComplaintId) return undefined;

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsRaiseModalOpen(false);
        setSelectedComplaintId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isRaiseModalOpen, selectedComplaintId]);

  const resetComplaintForm = () => {
    setForm({
      title: '',
      description: '',
      category: 'Plumbing',
      urgency: 'Medium',
      location: '',
      attachments: [],
    });
    setAttachmentError('');
  };

  const handleAttachments = async (event) => {
    const files = [...event.target.files];
    setAttachmentError('');

    if (form.attachments.length + files.length > 3) {
      setAttachmentError('You can attach up to three images.');
      return;
    }

    if (files.some((file) => !file.type.startsWith('image/'))) {
      setAttachmentError('Only image attachments are supported.');
      return;
    }

    if (files.some((file) => file.size > 700 * 1024)) {
      setAttachmentError('Each image must be smaller than 700 KB.');
      return;
    }

    try {
      const attachments = await Promise.all(files.map(readAttachment));
      setForm((current) => ({
        ...current,
        attachments: [...current.attachments, ...attachments],
      }));
    } catch (error) {
      setAttachmentError(
        error instanceof Error ? error.message : 'Unable to add attachments.'
      );
    }
  };

  const handleRaiseComplaint = (event) => {
    event.preventDefault();
    if (!form.title.trim() || !form.description.trim() || !form.location.trim()) {
      return;
    }

    const complaint = raiseComplaint(form);
    resetComplaintForm();
    setIsRaiseModalOpen(false);
    if (complaint) {
      setSelectedComplaintId(complaint.id);
    }
  };

  const openComplaint = (complaintId) => {
    markComplaintRead(complaintId);
    setSelectedComplaintId(complaintId);
    setComment('');
    setRating(0);
    setFeedback('');
    setIsReopening(false);
    setReopenReason('');
  };

  const handleComment = (event) => {
    event.preventDefault();
    if (!comment.trim() || !selectedComplaint) return;
    addComplaintComment(selectedComplaint.id, comment);
    setComment('');
  };

  const handleConfirmResolution = () => {
    if (!selectedComplaint || rating === 0) return;
    confirmComplaintResolution(selectedComplaint.id, { rating, feedback });
    setFeedback('');
  };

  const handleReopen = (event) => {
    event.preventDefault();
    if (!selectedComplaint || !reopenReason.trim()) return;
    reopenComplaint(selectedComplaint.id, reopenReason);
    setIsReopening(false);
    setReopenReason('');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
            My Complaints
          </h1>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Report an issue and follow every update through resolution.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setIsRaiseModalOpen(true)}
          className="flex items-center justify-center gap-1.5 self-start rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-colors hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          Raise Complaint
        </button>
      </div>

      <div className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="Search complaints, location, or technician..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          {['All', 'Active', 'Resolved'].map((status) => (
            <button
              type="button"
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-lg px-3 py-1.5 text-[10px] font-bold transition-colors ${
                statusFilter === status
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-50 text-slate-500 hover:text-slate-800'
              }`}
            >
              {status}
            </button>
          ))}
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
          >
            <option value="All">All categories</option>
            {CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
          <select
            value={urgencyFilter}
            onChange={(event) => setUrgencyFilter(event.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-600 focus:border-indigo-500 focus:outline-none"
          >
            <option value="All">All urgency</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
          <span className="ml-auto text-[10px] font-bold text-slate-400">
            {filteredComplaints.length} tickets
          </span>
        </div>
      </div>

      {filteredComplaints.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-14 text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-500" />
          <p className="mt-3 text-sm font-extrabold text-slate-700">
            No complaints found
          </p>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Try changing the filters or raise a new complaint.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredComplaints.map((complaint) => (
            <article
              key={complaint.id}
              role="button"
              tabIndex={0}
              onClick={() => openComplaint(complaint.id)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  openComplaint(complaint.id);
                }
              }}
              className="cursor-pointer rounded-2xl border border-slate-100 bg-white p-5 shadow-sm transition-all hover:border-indigo-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-100"
            >
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="truncate text-sm font-extrabold text-slate-800">
                      {complaint.title}
                    </h2>
                    {complaint.hasUnreadUpdate && (
                      <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[9px] font-extrabold text-white">
                        New update
                      </span>
                    )}
                    <span
                      className={`rounded-full px-2 py-0.5 text-[9px] font-extrabold ${URGENCY_STYLES[complaint.urgency]}`}
                    >
                      {complaint.urgency}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-xs font-semibold leading-relaxed text-slate-500">
                    {complaint.description}
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-semibold text-slate-400">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3.5 w-3.5" />
                      {complaint.location || complaint.flat}
                    </span>
                    <span className="flex items-center gap-1">
                      <UserRound className="h-3.5 w-3.5" />
                      {complaint.assignee || 'Awaiting assignment'}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock3 className="h-3.5 w-3.5" />
                      Updated {formatDateTime(getLatestUpdate(complaint))}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[10px] font-bold ${STATUS_STYLES[complaint.status]}`}
                  >
                    {complaint.status}
                  </span>
                  <ChevronRight className="h-4 w-4 text-slate-300" />
                </div>
              </div>
            </article>
          ))}
        </div>
      )}

      <section className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <HelpCircle className="h-4.5 w-4.5" />
          </div>
          <div>
            <h2 className="text-sm font-extrabold text-slate-800">
              Complaint FAQs
            </h2>
            <p className="mt-1 text-[11px] font-semibold text-slate-400">
              Quick answers about updates, resolution, and emergencies.
            </p>
          </div>
        </div>

        <div className="mt-4 divide-y divide-slate-100 border-t border-slate-100">
          {COMPLAINT_FAQS.map((faq) => {
            const isOpen = openFaqId === faq.id;
            return (
              <div key={faq.id}>
                <button
                  type="button"
                  onClick={() => setOpenFaqId(isOpen ? null : faq.id)}
                  className="flex w-full items-center justify-between gap-4 py-4 text-left"
                  aria-expanded={isOpen}
                >
                  <span className="text-xs font-bold text-slate-700">
                    {faq.question}
                  </span>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-slate-400 transition-transform ${
                      isOpen ? 'rotate-180' : ''
                    }`}
                  />
                </button>
                {isOpen && (
                  <p className="pb-4 pr-8 text-xs font-semibold leading-relaxed text-slate-500">
                    {faq.answer}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {isRaiseModalOpen && (
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setIsRaiseModalOpen(false);
            }
          }}
        >
          <div className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-3xl bg-white p-6 shadow-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-extrabold text-slate-900">
                  Raise a Complaint
                </h2>
                <p className="mt-1 text-xs font-semibold text-slate-400">
                  Add enough detail to help the team respond quickly.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setIsRaiseModalOpen(false)}
                aria-label="Close complaint form"
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleRaiseComplaint} className="mt-6 space-y-4">
              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Issue title
                </label>
                <input
                  autoFocus
                  required
                  value={form.title}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      title: event.target.value,
                    }))
                  }
                  placeholder="e.g. Leaking tap in kitchen"
                  className="w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Category
                  </label>
                  <select
                    value={form.category}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        category: event.target.value,
                      }))
                    }
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:outline-none"
                  >
                    {CATEGORIES.map((category) => (
                      <option key={category} value={category}>
                        {category}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Urgency
                  </label>
                  <select
                    value={form.urgency}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        urgency: event.target.value,
                      }))
                    }
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Exact location
                </label>
                <div className="relative">
                  <MapPin className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    required
                    value={form.location}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        location: event.target.value,
                      }))
                    }
                    placeholder="e.g. Kitchen, below the sink"
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Description
                </label>
                <textarea
                  required
                  rows={4}
                  value={form.description}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                  placeholder="Describe what happened and when it started..."
                  className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Photos
                </label>
                <label className="flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-xs font-bold text-slate-500 transition-colors hover:border-indigo-300 hover:text-indigo-600">
                  <Camera className="h-4 w-4" />
                  Add up to 3 photos
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleAttachments}
                    className="sr-only"
                  />
                </label>
                {attachmentError && (
                  <p className="text-[10px] font-semibold text-rose-600">
                    {attachmentError}
                  </p>
                )}
                {form.attachments.length > 0 && (
                  <div className="grid grid-cols-3 gap-2">
                    {form.attachments.map((attachment) => (
                      <div
                        key={attachment.id}
                        className="relative overflow-hidden rounded-xl border border-slate-100"
                      >
                        <img
                          src={attachment.dataUrl}
                          alt={attachment.name}
                          className="h-20 w-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            setForm((current) => ({
                              ...current,
                              attachments: current.attachments.filter(
                                (item) => item.id !== attachment.id
                              ),
                            }))
                          }
                          aria-label={`Remove ${attachment.name}`}
                          className="absolute right-1 top-1 rounded-full bg-slate-900/70 p-1 text-white"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
                <button
                  type="button"
                  onClick={() => {
                    resetComplaintForm();
                    setIsRaiseModalOpen(false);
                  }}
                  className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 hover:bg-indigo-700"
                >
                  <Send className="h-3.5 w-3.5" />
                  Submit Complaint
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {selectedComplaint && (
        <div
          className="fixed inset-0 z-[999] bg-slate-900/50 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              setSelectedComplaintId(null);
            }
          }}
        >
          <aside className="absolute inset-y-0 right-0 w-full max-w-2xl overflow-y-auto bg-white shadow-2xl">
            <div className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-slate-100 bg-white/95 px-6 py-5 backdrop-blur">
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
                  Ticket {selectedComplaint.id}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedComplaintId(null)}
                aria-label="Close complaint details"
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-6 p-6">
              <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                <p className="text-xs font-semibold leading-relaxed text-slate-600">
                  {selectedComplaint.description}
                </p>
                <div className="mt-4 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
                  <div className="flex gap-2">
                    <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Location
                      </p>
                      <p className="mt-0.5 font-bold text-slate-700">
                        {selectedComplaint.location || selectedComplaint.flat}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Assigned technician
                      </p>
                      <p className="mt-0.5 font-bold text-slate-700">
                        {selectedComplaint.assignee || 'Awaiting assignment'}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Expected resolution
                      </p>
                      <p className="mt-0.5 font-bold text-slate-700">
                        {formatDateTime(
                          getExpectedResolutionAt(selectedComplaint)
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                    <div>
                      <p className="text-[9px] font-bold uppercase tracking-wider text-slate-400">
                        Latest update
                      </p>
                      <p className="mt-0.5 font-bold text-slate-700">
                        {formatDateTime(getLatestUpdate(selectedComplaint))}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {(selectedComplaint.attachments ?? []).length > 0 && (
                <section>
                  <h3 className="flex items-center gap-2 text-sm font-extrabold text-slate-800">
                    <Paperclip className="h-4 w-4 text-indigo-500" />
                    Attachments
                  </h3>
                  <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {selectedComplaint.attachments.map((attachment) => (
                      <a
                        key={attachment.id}
                        href={attachment.dataUrl}
                        download={attachment.name}
                        className="overflow-hidden rounded-xl border border-slate-100"
                      >
                        <img
                          src={attachment.dataUrl}
                          alt={attachment.name}
                          className="h-24 w-full object-cover transition-transform hover:scale-105"
                        />
                      </a>
                    ))}
                  </div>
                </section>
              )}

              <section>
                <h3 className="text-sm font-extrabold text-slate-800">
                  Ticket timeline
                </h3>
                <div className="mt-4 space-y-0">
                  {getComplaintTimeline(selectedComplaint).map(
                    (event, index, events) => (
                      <div key={event.id} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <div
                            className={`h-3 w-3 rounded-full ${
                              index === events.length - 1
                                ? 'bg-indigo-600'
                                : 'bg-slate-300'
                            }`}
                          />
                          {index < events.length - 1 && (
                            <div className="h-full min-h-14 w-px bg-slate-200" />
                          )}
                        </div>
                        <div className="pb-5">
                          <p className="text-xs font-extrabold text-slate-700">
                            {event.label}
                          </p>
                          <p className="mt-1 text-[11px] font-semibold leading-relaxed text-slate-500">
                            {event.message}
                          </p>
                          <p className="mt-1 text-[9px] font-bold text-slate-400">
                            {event.actor} · {formatDateTime(event.createdAt)}
                          </p>
                        </div>
                      </div>
                    )
                  )}
                </div>
              </section>

              <section>
                <h3 className="flex items-center gap-2 text-sm font-extrabold text-slate-800">
                  <MessageSquare className="h-4 w-4 text-indigo-500" />
                  Conversation
                </h3>
                <div className="mt-3 space-y-3">
                  {(selectedComplaint.comments ?? []).length === 0 ? (
                    <p className="rounded-xl bg-slate-50 p-4 text-xs font-semibold text-slate-400">
                      No messages yet. Ask the assigned team for an update.
                    </p>
                  ) : (
                    selectedComplaint.comments.map((item) => (
                      <div
                        key={item.id}
                        className={`rounded-xl p-3 ${
                          item.authorRole === 'Resident'
                            ? 'ml-6 bg-indigo-50'
                            : 'mr-6 bg-slate-50'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[10px] font-extrabold text-slate-700">
                            {item.authorName}
                          </p>
                          <p className="text-[9px] font-semibold text-slate-400">
                            {formatDateTime(item.createdAt)}
                          </p>
                        </div>
                        <p className="mt-1 text-xs font-semibold leading-relaxed text-slate-600">
                          {item.message}
                        </p>
                      </div>
                    ))
                  )}
                </div>
                <form onSubmit={handleComment} className="mt-3 flex gap-2">
                  <input
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Write a message..."
                    className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                  />
                  <button
                    type="submit"
                    disabled={!comment.trim()}
                    className="rounded-xl bg-indigo-600 px-4 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                    aria-label="Send message"
                  >
                    <Send className="h-4 w-4" />
                  </button>
                </form>
              </section>

              {selectedComplaint.status === 'Resolved' && (
                <section className="rounded-2xl border border-emerald-100 bg-emerald-50/50 p-4">
                  {selectedComplaint.resolutionConfirmed ? (
                    <div>
                      <p className="flex items-center gap-2 text-sm font-extrabold text-emerald-800">
                        <CheckCircle2 className="h-4 w-4" />
                        Resolution confirmed
                      </p>
                      <div className="mt-2 flex gap-1">
                        {[1, 2, 3, 4, 5].map((value) => (
                          <Star
                            key={value}
                            className={`h-4 w-4 ${
                              value <= selectedComplaint.rating
                                ? 'fill-amber-400 text-amber-400'
                                : 'text-slate-300'
                            }`}
                          />
                        ))}
                      </div>
                      {selectedComplaint.residentFeedback && (
                        <p className="mt-2 text-xs font-semibold text-slate-600">
                          “{selectedComplaint.residentFeedback}”
                        </p>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div>
                        <p className="text-sm font-extrabold text-emerald-800">
                          Is the issue resolved?
                        </p>
                        <p className="mt-1 text-[11px] font-semibold text-emerald-700/70">
                          Rate the work or reopen the complaint if the issue
                          remains.
                        </p>
                      </div>
                      <div className="flex gap-1">
                        {[1, 2, 3, 4, 5].map((value) => (
                          <button
                            type="button"
                            key={value}
                            onClick={() => setRating(value)}
                            aria-label={`${value} stars`}
                          >
                            <Star
                              className={`h-6 w-6 ${
                                value <= rating
                                  ? 'fill-amber-400 text-amber-400'
                                  : 'text-slate-300'
                              }`}
                            />
                          </button>
                        ))}
                      </div>
                      <textarea
                        rows={2}
                        value={feedback}
                        onChange={(event) => setFeedback(event.target.value)}
                        placeholder="Optional feedback..."
                        className="w-full resize-none rounded-xl border border-emerald-100 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-emerald-400 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={handleConfirmResolution}
                        disabled={rating === 0}
                        className="rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                      >
                        Confirm Resolution
                      </button>
                    </div>
                  )}

                  <div className="mt-4 border-t border-emerald-100 pt-4">
                    {!isReopening ? (
                      <button
                        type="button"
                        onClick={() => setIsReopening(true)}
                        className="flex items-center gap-1.5 text-xs font-bold text-rose-600 hover:text-rose-700"
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                        Reopen this complaint
                      </button>
                    ) : (
                      <form onSubmit={handleReopen} className="space-y-2">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                          Why is the issue unresolved?
                        </label>
                        <textarea
                          required
                          rows={2}
                          value={reopenReason}
                          onChange={(event) =>
                            setReopenReason(event.target.value)
                          }
                          className="w-full resize-none rounded-xl border border-rose-100 bg-white px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-rose-400 focus:outline-none"
                        />
                        <div className="flex gap-2">
                          <button
                            type="submit"
                            className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-700"
                          >
                            Reopen Complaint
                          </button>
                          <button
                            type="button"
                            onClick={() => setIsReopening(false)}
                            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-600"
                          >
                            Cancel
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                </section>
              )}

              {selectedComplaint.status !== 'Resolved' &&
                new Date(getExpectedResolutionAt(selectedComplaint)) <
                  new Date() && (
                  <div className="flex gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs font-semibold text-amber-700">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    The expected resolution time has passed. Send a message to
                    request an update.
                  </div>
                )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
