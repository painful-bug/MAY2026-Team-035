const STEPS = [
  ['raised', 'Reported'], ['assigned', 'Assigned'], ['scheduled', 'Scheduled'],
  ['in_progress', 'In progress'], ['work_done', 'Work done'], ['closed', 'Closed'],
];

const typeOf = (event) => event.eventType || event.type || event.event_type;

export function canCancelUnstartedWork(events = []) {
  const latestAssignment = events.findLastIndex((event) =>
    ['job_assigned', 'job_scheduled'].includes(typeOf(event))
  );
  return latestAssignment >= 0 && !events.slice(latestAssignment + 1).some((event) =>
    ['job_started', 'job_completed'].includes(typeOf(event))
  );
}

export function projectTracker(events = []) {
  const all = [...events];
  const lastReopen = all.map(typeOf).lastIndexOf('reopened');
  const active = lastReopen >= 0 ? all.slice(lastReopen + 1) : all;
  const seen = new Set(active.map(typeOf));
  const completed = seen.has('job_completed') || seen.has('resolution_confirmed') || seen.has('auto_closed');
  const closed = seen.has('resolution_confirmed') || seen.has('auto_closed')
    || active.some((event) => typeOf(event) === 'status_changed' && (event.payload?.to === 'closed' || event.payload?.to === 'Closed'));
  const assigned = seen.has('job_assigned');
  const scheduled = seen.has('job_scheduled');
  const started = seen.has('job_started');
  const worker = active.find((event) => typeOf(event) === 'job_assigned')?.payload?.workerName
    || active.find((event) => typeOf(event) === 'job_assigned')?.payload?.assigneeName;
  const done = [true, assigned, scheduled, started, completed, closed];
  return {
    nodes: STEPS.map(([key, label], index) => ({
      key, label, state: done[index] ? 'done' : 'pending',
      detail: key === 'assigned' && worker ? `${worker} is coming.` : '',
      unrated: key === 'closed' && seen.has('auto_closed'),
    })),
    annotations: all.flatMap((event) => {
      const type = typeOf(event);
      const labels = { reopened: 'Reopened', returned_to_pool: 'Sent back for re-evaluation', job_failed: 'Visit unsuccessful' };
      return labels[type] ? [{ afterNode: type === 'job_failed' ? 'in_progress' : 'assigned', label: labels[type], at: event.createdAt || event.created_at }] : [];
    }),
  };
}
