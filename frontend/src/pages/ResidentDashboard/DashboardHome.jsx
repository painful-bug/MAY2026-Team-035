import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertTriangle,
  Bell,
  CalendarPlus,
  ChevronRight,
  CreditCard,
  Megaphone,
  UserPlus,
  Users,
} from 'lucide-react';
import { residentApi } from '../../features/resident/residentApi';
import { residentKeys, useResidentLiveUpdates } from '../../features/resident/residentEvents';
import { useApp } from '../../store/useApp';

// The resident's front page, over `GET /resident/snapshot` (API.md §14.5).
//
// **One read, not six.** The aggregate is a projection of the endpoints each
// card links to — the same `ResidentInvoice`, `VisitorPass`, `ComplaintSummary`
// and `Notice` those pages render — which is what stops the bill on this screen
// disagreeing with the bill on Payments. So there is no second query here for
// dues or visitors, and adding one would be re-introducing exactly the drift the
// aggregate exists to prevent.
//
// It replaces a read of the zustand demo store, whose shapes are gone rather
// than mapped: `visitor.flat`, `payment.amount`, `notice.date` and
// `complaint.timeAgo` were the prototype's invention and none of them is a field
// the API has. The store slices stay for the admin screens that still read them.
//
// Two quick actions used to open a modal here and now navigate. Creating a
// visitor pass shows a security code exactly once and settling a bill needs an
// idempotency key the client owns (§14.4): both are whole flows, both live on
// the page that owns them, and a second implementation of either on the home
// screen is a second place for them to be wrong. Approving a pass stays on the
// card — `visitors.pendingApproval` carries whole passes precisely so it can.

const NOTICE_STYLES = {
  Urgent: 'bg-rose-50 text-rose-700',
  Important: 'bg-amber-50 text-amber-700',
  Info: 'bg-blue-50 text-blue-700',
};

const COMPLAINT_STYLES = {
  Resolved: 'bg-emerald-50 text-emerald-700 border border-emerald-100',
  'In Progress': 'bg-blue-55/60 text-blue-700 border border-blue-100/50',
  Pending: 'bg-rose-50 text-rose-700 border border-rose-100',
  Cancelled: 'bg-slate-100 text-slate-500 border border-slate-200',
};

// Every money field on this API is a decimal string, not a number: the wire
// format is `"1200.00"` so that no amount is ever rounded by a float on the way
// through. Formatting is the one place it becomes a number.
const money = (value, currency = 'INR') => {
  const amount = Number(value ?? 0);
  if (Number.isNaN(amount)) return String(value ?? '');
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: currency || 'INR',
    maximumFractionDigits: 0,
  }).format(amount);
};

const shortDate = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date);
};

const relative = (value) => {
  if (!value) return '';
  const then = new Date(value);
  if (Number.isNaN(then.getTime())) return '';
  const minutes = Math.round((Date.now() - then.getTime()) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return shortDate(value);
};

const today = () =>
  new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });

function QuickAction({ icon: Icon, tone, title, subtitle, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-2xl border border-slate-100 bg-white p-4 text-left transition-all hover:border-indigo-200 hover:shadow-sm"
    >
      <div className={`mb-3 flex h-9 w-9 items-center justify-center rounded-xl ${tone}`}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <p className="text-sm font-extrabold text-slate-800">{title}</p>
      <div className="mt-1 text-[10px] font-semibold text-slate-400">{subtitle}</div>
    </button>
  );
}

function Card({ children, className = '' }) {
  return (
    <div className={`space-y-4 rounded-2xl border border-slate-100 bg-white p-6 ${className}`}>
      {children}
    </div>
  );
}

export default function DashboardHome() {
  const { currentUser, searchQuery } = useApp();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useResidentLiveUpdates();

  const snapshot = useQuery({
    queryKey: residentKeys.snapshot(),
    queryFn: () => residentApi.snapshot(),
  });

  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: residentKeys.snapshot() });

  const approve = useMutation({
    mutationFn: (passId) => residentApi.approveVisitorPass(passId),
    onSuccess: refresh,
  });
  const reject = useMutation({
    mutationFn: (passId) => residentApi.rejectVisitorPass(passId),
    onSuccess: refresh,
  });

  const data = snapshot.data;
  const dues = data?.dues;
  const visitors = data?.visitors;
  const primaryInvoice = dues?.primaryInvoice ?? null;

  // The header's search box is UI state and stays one: it narrows what is
  // already on screen. It is not a query parameter — neither the aggregate nor
  // the notice list accepts one, and inventing a client-side "search" that
  // silently only looks at the three newest notices would be worse than this.
  const term = (searchQuery || '').trim().toLowerCase();
  const matches = (...values) =>
    !term || values.some((value) => String(value || '').toLowerCase().includes(term));

  const notices = (data?.notices ?? []).filter((notice) =>
    matches(notice.title, notice.body)
  );
  const complaints = (data?.complaints?.recent ?? []).filter((complaint) =>
    matches(complaint.title, complaint.category, complaint.location)
  );
  const pending = visitors?.pendingApproval ?? [];

  if (snapshot.isLoading) {
    return (
      <div className="rounded-2xl border border-slate-100 bg-white px-6 py-16 text-center">
        <p className="text-sm font-bold text-slate-400">Loading your home…</p>
      </div>
    );
  }

  if (snapshot.error) {
    return (
      <div
        role="alert"
        className="space-y-3 rounded-2xl border border-rose-100 bg-rose-50 px-6 py-12 text-center"
      >
        <p className="text-sm font-extrabold text-rose-800">
          We could not load your home screen.
        </p>
        <p className="text-xs font-semibold text-rose-700">{snapshot.error.message}</p>
        <button
          type="button"
          onClick={() => snapshot.refetch()}
          className="rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-rose-700"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
            Good day, {currentUser?.name?.split(' ')[0] || 'neighbour'}
          </h1>
          <p className="mt-1 text-sm font-semibold text-slate-400">
            Here's what's happening in your apartment today.
          </p>
        </div>
        <div className="self-start rounded-2xl border border-slate-100 bg-white px-4 py-2 text-xs font-bold text-slate-500 shadow-sm sm:text-sm md:self-auto">
          {today()}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <QuickAction
          icon={UserPlus}
          tone="bg-indigo-50 text-indigo-600"
          title="Add Visitor"
          subtitle="Pre-approve a guest"
          onClick={() => navigate('/resident/visitors')}
        />
        <QuickAction
          icon={AlertTriangle}
          tone="bg-rose-50 text-rose-600"
          title="Raise Complaint"
          subtitle="Report an issue"
          onClick={() => navigate('/resident/complaints')}
        />
        <QuickAction
          icon={CalendarPlus}
          tone="bg-emerald-50 text-emerald-600"
          title="Book Amenity"
          subtitle="Gym, Club, Pool"
          onClick={() => navigate('/resident/amenities')}
        />
        <QuickAction
          icon={CreditCard}
          tone="bg-amber-50 text-amber-600"
          title="Pay Maintenance"
          onClick={() => navigate('/resident/payments')}
          subtitle={
            primaryInvoice ? (
              <span className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="text-base font-extrabold text-slate-800">
                  {money(primaryInvoice.outstandingAmount, primaryInvoice.currencyCode)}
                </span>
                {primaryInvoice.dueOn && (
                  <span className="text-[10px] font-semibold text-slate-400">
                    Due {shortDate(primaryInvoice.dueOn)}
                  </span>
                )}
              </span>
            ) : (
              <span className="font-semibold text-emerald-600">No maintenance dues</span>
            )
          }
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <Card>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Megaphone className="h-5 w-5 text-indigo-600" />
                <h3 className="text-base font-extrabold text-slate-800">Recent Notices</h3>
              </div>
              <button
                type="button"
                onClick={() => navigate('/resident/notices')}
                className="flex items-center gap-0.5 text-xs font-bold text-indigo-600 hover:text-indigo-700"
              >
                View all
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {notices.length === 0 ? (
              <p className="py-6 text-center text-xs font-semibold text-slate-400">
                {term ? 'No matching notices.' : 'Nothing has been posted yet.'}
              </p>
            ) : (
              <div className="divide-y divide-slate-50">
                {notices.map((notice) => (
                  <div
                    key={notice.id}
                    className="flex items-start justify-between gap-4 py-4 first:pt-0 last:pb-0"
                  >
                    <div className="flex gap-3">
                      <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-550">
                        <Megaphone className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-slate-800">{notice.title}</p>
                        <p className="mt-0.5 text-[11px] font-semibold text-slate-400">
                          {shortDate(notice.publishedAt)}
                          {notice.authorName ? ` · ${notice.authorName}` : ''}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[10px] font-extrabold ${
                        NOTICE_STYLES[notice.urgency] || NOTICE_STYLES.Info
                      }`}
                    >
                      {notice.urgency}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>

          <Card>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-indigo-650" />
                <h3 className="text-base font-extrabold text-slate-800">My Complaints</h3>
              </div>
              <button
                type="button"
                onClick={() => navigate('/resident/complaints')}
                className="flex items-center gap-0.5 text-xs font-bold text-indigo-650 hover:text-indigo-750"
              >
                View all
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {complaints.length === 0 ? (
              <div className="py-6 text-center text-xs font-semibold text-slate-400">
                {term
                  ? 'No matching complaints found.'
                  : 'No complaints filed yet. Use "Raise Complaint" above if something needs attention.'}
              </div>
            ) : (
              <div className="space-y-4">
                {complaints.slice(0, 2).map((complaint) => (
                  <button
                    key={complaint.id}
                    type="button"
                    onClick={() => navigate('/resident/complaints')}
                    className="w-full space-y-3.5 rounded-xl border border-slate-100 bg-slate-50/50 p-4 text-left"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h4 className="truncate text-sm font-extrabold text-slate-850">
                          {complaint.title}
                        </h4>
                        <p className="mt-0.5 text-[11px] font-semibold text-slate-450">
                          {complaint.assignee || 'Awaiting assignment'} ·{' '}
                          {relative(complaint.lastActivityAt)}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {complaint.isUnread && (
                          <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[9px] font-extrabold text-white">
                            New
                          </span>
                        )}
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                            COMPLAINT_STYLES[complaint.status] || COMPLAINT_STYLES.Pending
                          }`}
                        >
                          {complaint.status}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
                {data?.complaints?.total > complaints.length && (
                  <p className="text-[10px] font-bold text-slate-400">
                    {data.complaints.total} raised in total.
                  </p>
                )}
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <Card className="space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Users className="h-5 w-5 text-indigo-600" />
                <h3 className="text-sm font-extrabold text-slate-800">Visitors Today</h3>
              </div>
              <button
                type="button"
                onClick={() => navigate('/resident/visitors?view=history')}
                className="text-xs font-bold text-indigo-600 hover:underline"
              >
                History
              </button>
            </div>

            {/* Guests, not passes: one pass for a party of twelve counts as
                twelve, which is what a resident means by "how many are coming". */}
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl border border-slate-100/50 bg-slate-50/50 p-2.5">
                <p className="text-base font-extrabold text-slate-850">
                  {visitors?.expectedGuests ?? 0}
                </p>
                <p className="mt-0.5 text-[9px] font-bold uppercase text-slate-400">Expected</p>
              </div>
              <div className="rounded-xl border border-emerald-100/30 bg-emerald-50/20 p-2.5">
                <p className="text-base font-extrabold text-emerald-700">
                  {visitors?.checkedInGuests ?? 0}
                </p>
                <p className="mt-0.5 text-[9px] font-bold uppercase text-emerald-650">In</p>
              </div>
              <div className="rounded-xl border border-indigo-100/30 bg-indigo-50/20 p-2.5">
                <p className="text-base font-extrabold text-indigo-700">
                  {visitors?.pendingCount ?? 0}
                </p>
                <p className="mt-0.5 text-[9px] font-bold uppercase text-indigo-650">Pending</p>
              </div>
            </div>

            {pending.length > 0 ? (
              <div className="space-y-3">
                <p className="rounded-lg border border-indigo-100/30 bg-indigo-50/55 p-2 text-[10px] font-extrabold uppercase tracking-wide text-indigo-655">
                  {visitors.pendingCount} visitor request
                  {visitors.pendingCount === 1 ? '' : 's'} awaiting your approval
                </p>
                <div className="space-y-2.5">
                  {pending.map((pass) => (
                    <div
                      key={pass.id}
                      className="space-y-2.5 rounded-xl border border-slate-100 bg-slate-50 p-3"
                    >
                      <div>
                        <p className="text-xs font-bold text-slate-800">{pass.visitorName}</p>
                        <p className="text-[10px] font-semibold text-slate-450">
                          {pass.purposeDetails || pass.purpose}
                          {pass.validFrom ? ` · ${shortDate(pass.validFrom)}` : ''} ·{' '}
                          {pass.guestCount} guest{pass.guestCount === 1 ? '' : 's'}
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={() => approve.mutate(pass.id)}
                          disabled={approve.isPending || reject.isPending}
                          className="rounded-lg bg-indigo-600 py-1 text-[10px] font-bold text-white transition-colors hover:bg-indigo-750 disabled:bg-slate-300"
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => reject.mutate(pass.id)}
                          disabled={approve.isPending || reject.isPending}
                          className="rounded-lg border border-slate-200 py-1 text-[10px] font-bold text-slate-600 transition-colors hover:bg-slate-100 disabled:text-slate-300"
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {(approve.error || reject.error) && (
                  <p role="alert" className="text-[10px] font-semibold text-rose-600">
                    {(approve.error || reject.error).message}
                  </p>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 py-4 text-center text-xs font-semibold text-slate-400">
                No pending requests.
              </div>
            )}
          </Card>

          {primaryInvoice && (
            <div className="relative space-y-4 overflow-hidden rounded-2xl bg-indigo-600 p-6 text-white shadow-lg shadow-indigo-150">
              <div className="absolute bottom-0 right-0 h-32 w-32 translate-x-1/4 translate-y-1/4 rounded-full bg-white/10" />
              <div className="space-y-1">
                <span className="text-[9px] font-extrabold uppercase tracking-widest text-indigo-200">
                  {primaryInvoice.title}
                </span>
                <p className="text-3xl font-extrabold">
                  {money(primaryInvoice.outstandingAmount, primaryInvoice.currencyCode)}
                </p>
                <p className="text-[10px] font-semibold text-indigo-150">
                  {primaryInvoice.dueOn ? `Due ${shortDate(primaryInvoice.dueOn)}` : 'Payable now'}
                  {primaryInvoice.isOverdue ? ' · overdue' : ''}
                </p>
                {/* The total is a lower bound when the aggregate could not read
                    every unpaid bill. Saying so beats a number quietly too small:
                    a resident pays what they are shown and believes they are square. */}
                {dues?.unpaidCount > 1 && (
                  <p className="text-[10px] font-semibold text-indigo-150">
                    {dues.unpaidCount} unpaid ·{' '}
                    {money(dues.outstandingTotal, dues.currencyCode)}
                    {dues.isPartialTotal ? ' or more' : ''} outstanding
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => navigate('/resident/payments')}
                className="relative z-10 w-full rounded-xl bg-white/20 py-2.5 text-xs font-bold text-white backdrop-blur-sm transition-colors hover:bg-white/35"
              >
                {primaryInvoice.isPayable ? 'Pay Now' : 'View bill'}
              </button>
            </div>
          )}

          <Card className="space-y-3">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-indigo-600" />
              <h3 className="text-sm font-extrabold text-slate-800">Recent Activity</h3>
              {data?.unreadNotifications > 0 && (
                <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[10px] font-bold text-white">
                  {data.unreadNotifications}
                </span>
              )}
            </div>
            {(data?.activity ?? []).length === 0 ? (
              <p className="text-xs font-semibold text-slate-400">Nothing yet.</p>
            ) : (
              <ul className="space-y-2.5">
                {data.activity.map((item) => (
                  <li key={item.id} className="flex items-start gap-2">
                    {item.isUnread && (
                      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-500" />
                    )}
                    <div className="min-w-0">
                      <p className="truncate text-xs font-bold text-slate-700">{item.title}</p>
                      <p className="text-[10px] font-semibold text-slate-400">
                        {relative(item.createdAt)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
