import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ArrowUpCircle,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Inbox,
  PlayCircle,
  Plus,
  Timer,
  UserCheck,
  UserPlus,
} from 'lucide-react';

import AssignPickerModal from './AssignPickerModal';
import ComplaintDetailModal from './ComplaintDetailModal';
import TakeUpModal from './TakeUpModal';
import { NoteModal } from './NoteComposer';
import { CardActions, Chip, Empty, Failure, Section, whenText } from './triageParts';
import { openChatDock } from '../../features/messages/messagesApi';
import { triageApi } from '../../features/triage/triageApi';
import { usePortalScope } from '../../features/hiring/usePortalScope';
import { statusLabel, statusTone } from '../../features/workOrders/workOrderVocabulary';
import {
  canRaisePriority,
  categoryChipClass,
  complaintStatusChipClass,
  complaintStatusLabel,
  elapsedSince,
  nextPriority,
  pinUrgent,
  priorityChipClass,
  priorityLabel,
  raisePriorityBlockedReason,
  reassignmentBadges,
  workOrderBadges,
} from '../../lib/triageDisplay';

// The supervisor's landing surface.
//
// **What this replaces, and for whom.** A supervisor lands in `/worker` like
// every other service person — rank is not role (`0035`), so `_portal_for`
// sends the supervisor and the technician they dispatch to the same portal —
// and until now the landing page was `WorkerHome`: today's jobs, offers waiting
// on you, a link to your calendar. Every line of that is a technician's day. A
// supervisor holds no jobs; their day is the department's queue. `WorkerHome`
// is unchanged and still what a technician sees; `WorkerLanding` picks between
// the two on the roster rank the worker snapshot already carries.
//
// **Six sections, and the order is the work.** New complaints nobody has
// touched, the ones this supervisor has picked up, jobs waiting on the resident
// to name an hour, jobs raised that nobody has committed to, work somebody is
// booked for, and work happening right now. Reading down the page is reading
// the complaint's journey outward from the queue, and amendment 2's rule is
// that a complaint appears **once**: the furthest stage wins, so a complaint
// with a live job is that job in sections 3–6 and is not also a card in 1–2.
//
// The third section is ruling F1's: a resident-subject job now leaves the raise
// form with no hour on it, because the *resident* picks it, and it is not on
// the open pile until they do (or until the system books it for them 24 hours
// later). It sits between "taken up" and "open requests" because that is where
// it is in the journey — raised, and not yet anybody's to claim.
//
// **The browser does not decide which section a row is in.** One read,
// `GET /departments/{id}/triage-snapshot`, answers with six arrays already
// bucketed, and the contract (`docs/plans/SUPERVISOR_TRIAGE_SPEC.md`) states the
// rule outright: *the frontend renders the arrays as-is and never re-buckets*.
// The definitions are genuinely intricate — an offered-but-unaccepted job is an
// *open request* and not an assignment, because ruling A3 says a worker has to
// commit before the department stops looking for one — and a second copy of them
// here would be a second copy that goes wrong quietly. The one rearrangement
// this file makes is the urgent *stack*: a stable sort inside section 1, which
// the spec pins on the client deliberately.
//
// **Three verbs on every card, whatever the stage.** Eye, chat, note — look at
// it, ask about it, write something down about it. They are universal because
// none of them is stage-specific: a supervisor watching a job that is under way
// still needs to reach the resident, and the two monitor-only sections would
// otherwise be a wallboard you cannot act from.
//
// **The endpoints are not all live yet.** The migration that adds `taken_up_at`,
// `started_at`, `supervision_inherited_at`, the complaint chat thread and the
// amendment-2 RPCs is hand-applied by the owner; on a backend without it these
// calls 404 and this page renders its failure lines. That is expected, not a
// defect, and it is why the tests mock the boundary.

// ---------------------------------------------------------------------------
// Small pieces
// ---------------------------------------------------------------------------

const primaryButton =
  'inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:opacity-60';
const quietButton =
  'inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50';

/**
 * One card, in every section.
 *
 * Phase one had a full card in section 1 and a title-and-chip row everywhere
 * else, because sections 2–4 were waiting on product review. They are not any
 * more, and `MinimalRow` is gone: a supervisor deciding whether to step into a
 * job that has been "under way" for four hours needs the same face on it as the
 * one deciding whether to take a complaint up.
 */
function TriageCard({
  subject,
  title,
  subtitle,
  priority,
  category,
  statusChip,
  badges = [],
  meta,
  complaintId,
  actions,
  error,
  onOpen,
  onChat,
  onNote,
  chatPending,
}) {
  return (
    <article className="space-y-3 rounded-2xl border border-slate-100 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-extrabold text-slate-800">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 truncate text-[11px] font-semibold text-slate-400">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {/* Both chips carry their word. The colour is the fast read across a
              page of cards; the label is the one that works for everybody. */}
          <Chip className={priorityChipClass(priority)}>{priorityLabel(priority)}</Chip>
          {category ? <Chip className={categoryChipClass(category)}>{category}</Chip> : null}
        </div>
      </div>

      {statusChip || badges.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {statusChip ? <Chip className={statusChip.className}>{statusChip.label}</Chip> : null}
          {/* Why a row is not where you would expect it — bounced back, reopened,
              moved in from another department, or inherited from somebody who
              left. A job that has bounced twice is a different conversation from
              one raised this morning. */}
          {badges.map((badge) => (
            <Chip key={badge} className="bg-amber-50 text-amber-700 ring-amber-200">{badge}</Chip>
          ))}
        </div>
      ) : null}

      {meta ? <p className="text-[11px] font-bold text-slate-400">{meta}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-50 pt-3">
        <CardActions
          subject={subject}
          complaintId={complaintId}
          onOpen={onOpen}
          onChat={onChat}
          onNote={onNote}
          chatPending={chatPending}
        />
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>

      {/* The refusal belongs on the card that was refused, not in a banner. A
          409 names whoever got there first, or the running job that has to
          finish before this can be resolved, and that sentence is only useful
          beside the row it is about. */}
      <Failure error={error} />
    </article>
  );
}

/**
 * A clock for section 5, ticking once a minute for the whole page.
 *
 * Mount-computed would have been less code and would have been wrong on the
 * screen this page is: a supervisor leaves this open all shift, and a card that
 * says "under way 5m" three hours later is worse than no number, because it
 * reads as fresh. One interval for the page rather than one per card, and none
 * at all when nothing is under way.
 */
function useNow(active) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

// ---------------------------------------------------------------------------
// The screen
// ---------------------------------------------------------------------------

export default function SupervisorDashboard({ engagement }) {
  const queryClient = useQueryClient();
  const departmentId = engagement?.departmentId || null;
  // Only the *base* comes from the portal scope. Its `departmentId` falls back
  // to the membership's, which is right for a manager and wrong here: a
  // supervisor's department is on the roster row, which is what `engagement`
  // carries. The base is what keeps this link inside `/worker` instead of
  // sending a supervisor into the admin portal.
  const { base } = usePortalScope();

  // Which popup is open, if any: `{ kind, complaintId, ... }`. One piece of
  // state rather than three booleans, because exactly one of them is open at a
  // time and three booleans is how two of them end up open at once.
  const [popup, setPopup] = useState(null);
  // The complaint whose "Resolved" has been pressed once. Resolve cancels every
  // unstarted job on the complaint and notifies the workers holding them, which
  // is too much to do on a single click of a small button.
  const [confirming, setConfirming] = useState(null);

  const snapshot = useQuery({
    queryKey: ['supervisor-triage', departmentId],
    queryFn: () => triageApi.snapshot(departmentId),
    enabled: Boolean(departmentId),
    // The fallback half of the refresh rule. The event below is the fast path;
    // this is what covers a tab that has been open with no SSE beat.
    staleTime: 60_000,
  });

  // This page is react-query and the SSE stream is not, so the re-snapshot that
  // ticks the notification bell would leave the queue behind it stale.
  // `DashboardDataBootstrap` already dispatches this window event after every
  // beat, so hanging the invalidation off it keeps the two in step without a
  // second EventSource — the pattern `PendingRegistrations.jsx` set.
  useEffect(() => {
    const onRefresh = () => queryClient.invalidateQueries({ queryKey: ['supervisor-triage'] });
    window.addEventListener('homebandhu:dashboard-refresh', onRefresh);
    return () => window.removeEventListener('homebandhu:dashboard-refresh', onRefresh);
  }, [queryClient]);

  // The complaint leaves one section and appears in another, and which of those
  // happens is the server's answer and not this screen's guess — so every
  // success path re-reads rather than moving a card locally.
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['supervisor-triage'] });

  const takeUp = useMutation({
    mutationFn: (complaintId) => triageApi.takeUp(complaintId),
    onSuccess: invalidate,
  });

  const resolve = useMutation({
    mutationFn: (complaintId) => triageApi.resolve(complaintId),
    onSuccess: () => {
      setConfirming(null);
      invalidate();
    },
  });

  const raisePriority = useMutation({
    mutationFn: (complaintId) => triageApi.raisePriority(complaintId),
    onSuccess: invalidate,
  });

  // Open-or-get, then hand the id to the dock. The dock is mounted once in
  // `App.jsx` outside `<Routes>`, so a window event is how anything reaches it —
  // the mechanism `openChatDock` already exists for.
  const chat = useMutation({
    mutationFn: (complaintId) => triageApi.openChat(complaintId),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['dm-threads'] });
      openChatDock({ threadId: data?.threadId });
    },
  });

  // `awaitingResident` defaults with the rest, and the default is load-bearing
  // for once: the bucket arrives with the migration behind ruling F1, so a
  // backend that has not been updated yet answers without the key rather than
  // with an empty array.
  const {
    newComplaints = [],
    takenUp = [],
    awaitingResident = [],
    openRequests = [],
    assignedPending = [],
    inProgress = [],
  } = snapshot.data ?? {};

  const now = useNow(inProgress.length > 0);

  if (!departmentId) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        No department is attached to your posting yet, so there is no queue to
        show. An administrator sets this when they add you to a department.
      </p>
    );
  }

  if (snapshot.isPending) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Loading your department…</p>;
  }

  if (snapshot.isError) {
    return (
      <div className="space-y-3 rounded-2xl border border-rose-100 bg-white p-6">
        <Failure error={snapshot.error} />
        <button type="button" onClick={() => snapshot.refetch()} className={quietButton}>
          Try again
        </button>
      </div>
    );
  }

  // Every refusal that belongs to one row, whichever verb produced it. The
  // mutations are per-page and their `variables` name the complaint, which is
  // what keeps a 409 on the card it was about instead of in a banner over
  // twenty of them.
  const errorFor = (complaintId) => {
    for (const mutation of [takeUp, resolve, raisePriority, chat]) {
      if (mutation.error && mutation.variables === complaintId) return mutation.error;
    }
    return null;
  };
  const busy = (mutation, complaintId) => mutation.isPending && mutation.variables === complaintId;

  const universal = (subject, complaintId, extra = {}) => ({
    subject,
    complaintId,
    chatPending: busy(chat, complaintId),
    onOpen: () => setPopup({ kind: 'detail', complaintId, ...extra }),
    onChat: () => chat.mutate(complaintId),
    onNote: () => setPopup({ kind: 'note', complaintId, title: extra.title || subject }),
  });

  // --- the stage verbs, one definition each -------------------------------
  // Each returns the same node for the card and for the eye popup, because
  // "the stage's primary actions repeated inside" has to mean the same buttons
  // and not a second implementation of them.

  const takeUpButton = (complaint) => (
    <button
      type="button"
      disabled={busy(takeUp, complaint.id)}
      onClick={() => takeUp.mutate(complaint.id)}
      className={primaryButton}
    >
      <UserCheck className="h-4 w-4" />
      {busy(takeUp, complaint.id) ? 'Taking it up…' : 'Take up'}
    </button>
  );

  const resolveButton = (complaintId, label) =>
    confirming === complaintId ? (
      <span className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold text-slate-500">
          Resolve this? Unstarted jobs on it are called off and their workers told.
        </span>
        <button
          type="button"
          disabled={busy(resolve, complaintId)}
          onClick={() => resolve.mutate(complaintId)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-60"
        >
          <CheckCircle2 className="h-4 w-4" />
          {busy(resolve, complaintId) ? 'Resolving…' : 'Yes, resolve it'}
        </button>
        <button type="button" onClick={() => setConfirming(null)} className={quietButton}>
          Back
        </button>
      </span>
    ) : (
      <button type="button" onClick={() => setConfirming(complaintId)} className={quietButton}>
        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
        {label}
      </button>
    );

  // The established mechanism, not a second raise form (ruling A6): the
  // work-order queue's own raise tab, deep-linked at the complaint. Portal-
  // relative, so a supervisor stays in `/worker`.
  const raiseJobLink = (complaintId) => (
    <Link
      to={`${base}/departments/${departmentId}/work-orders?tab=raise&complaint=${complaintId}`}
      className={primaryButton}
    >
      <Plus className="h-4 w-4" />
      Raise job request
    </Link>
  );

  // Navigation, and deliberately nothing else. A job waiting on the resident's
  // hour has no supervisor verb on it — the answer belongs to somebody who is
  // not on this screen, and the 24-hour timer belongs to the engine — so the
  // one thing offered is the way to go and look at the job's whole history.
  // `?job=` is the parameter `0037`'s supervisor notifications already carry.
  const queueLink = (order) => (
    <Link
      to={`${base}/departments/${departmentId}/work-orders?tab=queue&job=${order.id}`}
      className={quietButton}
    >
      <ClipboardList className="h-4 w-4" />
      Open in the work-order queue
    </Link>
  );

  const priorityButton = (complaintId, priority) => {
    const blocked = raisePriorityBlockedReason(priority);
    return (
      <button
        type="button"
        title={blocked || `Raise this to ${nextPriority(priority)}. It cannot be lowered again.`}
        disabled={Boolean(blocked) || busy(raisePriority, complaintId)}
        onClick={() => raisePriority.mutate(complaintId)}
        className={quietButton}
      >
        <ArrowUpCircle className="h-4 w-4 text-rose-500" />
        {busy(raisePriority, complaintId)
          ? 'Raising…'
          : canRaisePriority(priority)
            ? `Raise priority to ${nextPriority(priority)}`
            : 'Already High'}
      </button>
    );
  };

  const takenUpActions = (complaint) => (
    <>
      {raiseJobLink(complaint.id)}
      {resolveButton(complaint.id, 'Resolved')}
    </>
  );

  // The exception valve of ruling R8, and the quiet style is the ruling: *"it
  // sholdnt be something seen in normal routine workflow … it is available at
  // any time though but as a seperate button"*. Leadership is not a candidate
  // anywhere (ruling R1 filters `dispatch_candidates` to `rank = 'member'`), so
  // this is not a shortcut through the picker beside it — it is its own call,
  // with no id in the body, and the modal says what stepping outside the norm
  // means before it fires.
  const takeUpJobButton = (order) => (
    <button
      type="button"
      onClick={() => setPopup({ kind: 'takeup', order })}
      className={quietButton}
    >
      <UserCheck className="h-4 w-4 text-indigo-600" />
      Take this job myself
    </button>
  );

  const openRequestActions = (order) => (
    <>
      <button
        type="button"
        onClick={() => setPopup({ kind: 'assign', order })}
        className={primaryButton}
      >
        <UserPlus className="h-4 w-4" />
        Assign without asking
      </button>
      {takeUpJobButton(order)}
      {order.complaintId ? priorityButton(order.complaintId, order.priority) : null}
      {order.complaintId ? resolveButton(order.complaintId, 'Mark as resolved') : null}
    </>
  );

  // --- the cards ------------------------------------------------------------

  const complaintSubtitle = (complaint) =>
    [complaint.raisedBy || 'Somebody in this community', complaint.unitCode, complaint.location]
      .filter(Boolean)
      .join(' · ');

  const complaintMeta = (complaint) => {
    const raised = whenText(complaint.createdAt);
    const due = whenText(complaint.dueAt);
    return [
      raised ? `Raised ${raised}` : 'Raised recently',
      due ? `due ${due}` : null,
      complaint.takenUpByName ? `taken up by ${complaint.takenUpByName}` : null,
      complaint.liveWorkOrderCount > 0
        ? `${complaint.liveWorkOrderCount} live ${complaint.liveWorkOrderCount === 1 ? 'job' : 'jobs'}`
        : null,
    ].filter(Boolean).join(' · ');
  };

  const complaintCard = (complaint, { stage, actions, withStatus = false }) => (
    <TriageCard
      key={complaint.id}
      title={complaint.title}
      subtitle={complaintSubtitle(complaint)}
      priority={complaint.priority}
      category={complaint.category}
      statusChip={
        withStatus
          ? {
            label: complaintStatusLabel(complaint.status),
            className: complaintStatusChipClass(complaint.status),
          }
          : null
      }
      badges={reassignmentBadges(complaint)}
      meta={complaintMeta(complaint)}
      actions={actions?.(complaint)}
      error={errorFor(complaint.id)}
      {...universal(complaint.title, complaint.id, {
        stage,
        title: complaint.title,
        subtitle: complaintSubtitle(complaint),
        priority: complaint.priority,
        category: complaint.category,
        status: complaint.status,
        location: complaint.location,
        reroutedAt: complaint.reroutedAt,
        takenUpByName: complaint.takenUpByName,
      })}
    />
  );

  const orderMeta = (order, { elapsed = false } = {}) => {
    const scheduled = whenText(order.scheduledStartAt);
    return [
      order.skillName,
      elapsed && order.startedAt
        ? `Started ${whenText(order.startedAt)} · under way ${elapsedSince(order.startedAt, now)}`
        : scheduled ? `Booked for ${scheduled}` : 'No time set yet',
      order.assigneeName ? `${order.assigneeName} holds it` : null,
      // §3's own line, and the reason ruling A3 moved this card out of
      // "assigned": somebody has been asked and has not said yes.
      order.offeredToName ? `Offered to ${order.offeredToName}, awaiting acceptance` : null,
    ].filter(Boolean).join(' · ');
  };

  const orderCard = (order, { stage, actions, elapsed = false }) => (
    <TriageCard
      key={order.id}
      title={order.complaintTitle || 'Work with no complaint title'}
      subtitle={[order.locationText, order.skillName].filter(Boolean).join(' · ')}
      priority={order.priority}
      category={order.complaintCategory}
      statusChip={{ label: statusLabel(order.status), className: statusTone(order.status) }}
      badges={workOrderBadges(order)}
      meta={orderMeta(order, { elapsed })}
      actions={actions?.(order)}
      error={order.complaintId ? errorFor(order.complaintId) : null}
      {...universal(order.complaintTitle || 'this job', order.complaintId, {
        stage,
        title: order.complaintTitle,
        subtitle: [order.locationText, order.skillName].filter(Boolean).join(' · '),
        priority: order.priority,
        category: order.complaintCategory,
        location: order.locationText,
        order,
      })}
    />
  );

  const { urgent, rest } = pinUrgent(newComplaints);
  const newCard = (complaint) =>
    complaintCard(complaint, { stage: 'New complaint', actions: takeUpButton });

  // The buttons the eye popup repeats, chosen from the section the card was in.
  const popupActions = () => {
    if (!popup || popup.kind !== 'detail') return null;
    const complaint = { id: popup.complaintId, priority: popup.priority, title: popup.title };
    if (popup.stage === 'New complaint') return takeUpButton(complaint);
    if (popup.stage === 'Taken up by you') return takenUpActions(complaint);
    if (popup.stage === 'Open job request') return openRequestActions(popup.order);
    if (popup.stage === 'Awaiting resident response') {
      return popup.order ? queueLink(popup.order) : null;
    }
    return (
      <p className="text-[11px] font-semibold text-slate-400">
        Nothing to press here: the job is with a worker now. Cancelling or moving
        it is the work-order queue&apos;s job, where the whole history of the
        booking is.
      </p>
    );
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">
          {engagement?.departmentName || 'Your department'}
        </h1>
        <p className="mt-1 text-sm font-medium text-slate-500">
          {engagement?.communityName || 'The community'} ·{' '}
          {newComplaints.length} waiting · {openRequests.length} unclaimed ·{' '}
          {inProgress.length} under way
        </p>
      </div>

      <Section
        id="triage-new"
        title="New complaints"
        count={newComplaints.length}
        blurb="Nobody has picked these up. Urgent ones are pinned to the top."
      >
        {newComplaints.length === 0 ? (
          <Empty icon={Inbox}>
            Nothing new is waiting. Every complaint routed here has been picked
            up by somebody.
          </Empty>
        ) : (
          <div className="space-y-4">
            {urgent.length > 0 ? (
              <div className="space-y-3 rounded-3xl border border-rose-100 bg-rose-50/40 p-3">
                <p className="px-1 text-[11px] font-extrabold uppercase tracking-wider text-rose-600">
                  Urgent · {urgent.length}
                </p>
                <div className="grid gap-3 lg:grid-cols-2">{urgent.map(newCard)}</div>
              </div>
            ) : null}
            {rest.length > 0 ? (
              <div className="grid gap-3 lg:grid-cols-2">{rest.map(newCard)}</div>
            ) : null}
          </div>
        )}
      </Section>

      <Section
        id="triage-taken-up"
        title="Taken up by you"
        count={takenUp.length}
        blurb="You own the triage; no job has been raised yet."
      >
        {takenUp.length === 0 ? (
          <Empty icon={ClipboardCheck}>
            You have not taken anything up. Pressing <b>Take up</b> above moves a
            complaint here and tells the resident it is in progress.
          </Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {takenUp.map((complaint) =>
              complaintCard(complaint, {
                stage: 'Taken up by you',
                actions: takenUpActions,
                withStatus: true,
              }))}
          </div>
        )}
      </Section>

      <Section
        id="triage-awaiting-resident"
        title="Awaiting resident response"
        count={awaitingResident.length}
        blurb="Raised, and the resident is choosing the hour. Nobody can claim these until they do."
      >
        {awaitingResident.length === 0 ? (
          <Empty icon={CalendarClock}>
            No resident is being waited on. A job appears here the moment one is
            raised against somebody&apos;s home, and leaves it when they pick a
            time — or 24 hours later, when the system picks one for them.
          </Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {awaitingResident.map((order) =>
              orderCard(order, { stage: 'Awaiting resident response' }))}
          </div>
        )}
      </Section>

      <Section
        id="triage-open-requests"
        title="Open job requests"
        count={openRequests.length}
        blurb="Raised, and nobody has committed. An offer sitting unanswered is still open."
      >
        {openRequests.length === 0 ? (
          <Empty icon={Timer}>
            Nothing is waiting on a worker. Every job this department has raised
            has somebody who said yes to it.
          </Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {openRequests.map((order) =>
              orderCard(order, { stage: 'Open job request', actions: openRequestActions }))}
          </div>
        )}
      </Section>

      <Section
        id="triage-assigned"
        title="Assigned, work pending"
        count={assignedPending.length}
        blurb="A worker has committed and has not started. Watch it; the queue is where you change it."
      >
        {assignedPending.length === 0 ? (
          <Empty icon={ClipboardCheck}>
            Nobody is booked on anything. Raise a job from a complaint above to
            put somebody on it.
          </Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {assignedPending.map((order) => orderCard(order, { stage: 'Assigned, work pending' }))}
          </div>
        )}
      </Section>

      <Section
        id="triage-in-progress"
        title="Being worked right now"
        count={inProgress.length}
        blurb="The worker has pressed Start. The clock is since then."
      >
        {inProgress.length === 0 ? (
          <Empty icon={PlayCircle}>
            Nothing is under way this minute. A job appears here the moment the
            worker presses Start.
          </Empty>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {inProgress.map((order) =>
              orderCard(order, { stage: 'Being worked right now', elapsed: true }))}
          </div>
        )}
      </Section>

      {popup?.kind === 'detail' ? (
        <ComplaintDetailModal
          complaintId={popup.complaintId}
          fallback={popup}
          stage={popup.stage}
          actions={
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">{popupActions()}</div>
              <Failure error={errorFor(popup.complaintId)} />
            </div>
          }
          onClose={() => setPopup(null)}
        />
      ) : null}

      {popup?.kind === 'note' ? (
        <NoteModal
          complaintId={popup.complaintId}
          title={popup.title}
          onClose={() => setPopup(null)}
        />
      ) : null}

      {popup?.kind === 'assign' ? (
        <AssignPickerModal order={popup.order} onClose={() => setPopup(null)} />
      ) : null}

      {popup?.kind === 'takeup' ? (
        <TakeUpModal order={popup.order} onClose={() => setPopup(null)} />
      ) : null}
    </div>
  );
}
