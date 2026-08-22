import { describe, expect, it } from 'vitest';

import {
  canRaisePriority,
  categoryChipClass,
  complaintStatusChipClass,
  complaintStatusLabel,
  elapsedSince,
  isUrgent,
  nextPriority,
  pinUrgent,
  priorityChipClass,
  priorityLabel,
  raisePriorityBlockedReason,
  reassignmentBadges,
  staffComplaintFields,
  timelineEntries,
  workOrderBadges,
} from './triageDisplay';

// The spec froze these, so they are tested as promises rather than as
// implementation: a category is the same colour everywhere, a priority is the
// colour the spec named *and* carries its word, and pinning the urgent stack is
// a sort that cannot lose a row.

describe('categoryChipClass', () => {
  it('gives the same category the same colour every time', () => {
    const first = categoryChipClass('Plumbing');
    for (let i = 0; i < 20; i += 1) {
      expect(categoryChipClass('Plumbing')).toBe(first);
    }
  });

  it('ignores case and surrounding space, so one trade is one colour', () => {
    const canonical = categoryChipClass('Plumbing');
    expect(categoryChipClass('plumbing')).toBe(canonical);
    expect(categoryChipClass('  PLUMBING  ')).toBe(canonical);
  });

  it('never leaves a chip without classes, whatever it is handed', () => {
    for (const value of [null, undefined, '', '   ', 0, 'Électricité', '💧']) {
      expect(categoryChipClass(value)).toMatch(/\bbg-/);
      expect(categoryChipClass(value)).toMatch(/\btext-/);
    }
  });

  it('spreads real category names over the whole palette', () => {
    // Not a distribution proof — a guard against a hash that collapses. Eight
    // distinct trades landing on one or two colours would make the chip
    // decorative rather than informative.
    const trades = [
      'Plumbing', 'Electrical', 'Housekeeping', 'Carpentry', 'Security',
      'Gardening', 'Lifts', 'Pest control', 'Painting', 'Water supply',
    ];
    const colours = new Set(trades.map(categoryChipClass));
    expect(colours.size).toBeGreaterThanOrEqual(4);
  });

  it('keeps clear of the priority tones', () => {
    // A category chip that came out rose would read as "High" at a glance,
    // which is the one confusion this palette exists to avoid.
    const trades = ['Plumbing', 'Electrical', 'Housekeeping', 'Carpentry', 'Security', 'Gardening'];
    for (const trade of trades) {
      expect(categoryChipClass(trade)).not.toMatch(/rose|amber/);
    }
  });
});

describe('priorityChipClass and priorityLabel', () => {
  it('uses the three tones the spec named', () => {
    expect(priorityChipClass('High')).toMatch(/rose/);
    expect(priorityChipClass('Medium')).toMatch(/amber/);
    expect(priorityChipClass('Low')).toMatch(/slate/);
  });

  it('reads the wire vocabulary whatever its case', () => {
    expect(priorityChipClass('high')).toBe(priorityChipClass('High'));
    expect(priorityChipClass(' HIGH ')).toBe(priorityChipClass('High'));
  });

  it('always has a word, because colour alone is not a label', () => {
    expect(priorityLabel('High')).toBe('High');
    expect(priorityLabel('medium')).toBe('Medium');
    expect(priorityLabel(null)).toBe('Unrated');
    expect(priorityLabel('critical')).toBe('Critical');
  });

  it('falls back rather than rendering an unstyled chip', () => {
    expect(priorityChipClass('critical')).toBe(priorityChipClass('Low'));
  });
});

describe('pinUrgent', () => {
  const rows = [
    { id: 'a', priority: 'Medium' },
    { id: 'b', priority: 'High' },
    { id: 'c', priority: 'Low' },
    { id: 'd', priority: 'high' },
  ];

  it('lifts High to the top and leaves everything else in server order', () => {
    const { urgent, rest } = pinUrgent(rows);
    expect(urgent.map((row) => row.id)).toEqual(['b', 'd']);
    expect(rest.map((row) => row.id)).toEqual(['a', 'c']);
  });

  it('loses nothing and invents nothing — this is a sort, not a bucket', () => {
    const { urgent, rest } = pinUrgent(rows);
    expect([...urgent, ...rest]).toHaveLength(rows.length);
    expect(new Set([...urgent, ...rest].map((row) => row.id)).size).toBe(rows.length);
  });

  it('survives an empty or absent array', () => {
    expect(pinUrgent([])).toEqual({ urgent: [], rest: [] });
    expect(pinUrgent(undefined)).toEqual({ urgent: [], rest: [] });
    expect(pinUrgent(null)).toEqual({ urgent: [], rest: [] });
  });

  it('treats an unrated complaint as ordinary, never as urgent', () => {
    const { urgent, rest } = pinUrgent([{ id: 'x', priority: null }]);
    expect(urgent).toHaveLength(0);
    expect(rest.map((row) => row.id)).toEqual(['x']);
  });
});

describe('isUrgent', () => {
  it('is High and nothing else', () => {
    expect(isUrgent('High')).toBe(true);
    expect(isUrgent('high')).toBe(true);
    expect(isUrgent('Medium')).toBe(false);
    expect(isUrgent(null)).toBe(false);
  });
});

describe('reassignmentBadges', () => {
  it('says nothing about a complaint raised once and never moved', () => {
    expect(reassignmentBadges({ reopenedCount: 0 })).toEqual([]);
  });

  it('names each of the three reasons a complaint is back in the new pile', () => {
    expect(reassignmentBadges({ returnedToPoolAt: '2026-08-22T09:00:00Z' }))
      .toEqual(['Returned to pool']);
    expect(reassignmentBadges({ reopenedCount: 3 })).toEqual(['Reopened ×3']);
    expect(reassignmentBadges({ reroutedAt: '2026-08-22T09:00:00Z' }))
      .toEqual(['Moved to this department']);
  });

  it('shows all three at once when all three are true', () => {
    expect(reassignmentBadges({
      returnedToPoolAt: '2026-08-22T09:00:00Z',
      reopenedCount: 2,
      reroutedAt: '2026-08-22T10:00:00Z',
    })).toEqual(['Returned to pool', 'Reopened ×2', 'Moved to this department']);
  });
});

describe('workOrderBadges', () => {
  it('says nothing about a job whose supervision never moved', () => {
    expect(workOrderBadges({ inheritedAt: null })).toEqual([]);
    expect(workOrderBadges(undefined)).toEqual([]);
  });

  it('marks a job re-stamped onto this supervisor by a departure', () => {
    expect(workOrderBadges({ inheritedAt: '2026-08-21T09:00:00Z' })).toEqual(['Inherited']);
  });
});

describe('complaintStatusLabel', () => {
  it('translates the storage words the staff detail answers with', () => {
    // `staff_complaint_detail` hands back the row as Postgres wrote it, so this
    // screen sees `open` where the snapshot sends `Pending`.
    expect(complaintStatusLabel('open')).toBe('Pending');
    expect(complaintStatusLabel('acknowledged')).toBe('In Progress');
    expect(complaintStatusLabel('in_progress')).toBe('In Progress');
    // The backend's own asymmetry, kept rather than corrected: the frontend
    // vocabulary has no fourth word for closed.
    expect(complaintStatusLabel('closed')).toBe('Resolved');
    expect(complaintStatusLabel('cancelled')).toBe('Cancelled');
  });

  it('passes a wire word through as itself', () => {
    expect(complaintStatusLabel('Pending')).toBe('Pending');
    expect(complaintStatusLabel('In Progress')).toBe('In Progress');
    expect(complaintStatusLabel('Resolved')).toBe('Resolved');
  });

  it('never renders an empty chip', () => {
    expect(complaintStatusLabel(null)).toBe('Pending');
    expect(complaintStatusLabel('escalated')).toBe('Escalated');
    expect(complaintStatusChipClass('anything')).toMatch(/\bbg-/);
  });
});

describe('elapsedSince', () => {
  const start = Date.parse('2026-08-22T08:00:00Z');

  it('counts minutes, then hours and minutes', () => {
    expect(elapsedSince('2026-08-22T08:00:00Z', start + 40 * 60_000)).toBe('40m');
    expect(elapsedSince('2026-08-22T08:00:00Z', start + 95 * 60_000)).toBe('1h 35m');
    expect(elapsedSince('2026-08-22T08:00:00Z', start + 120 * 60_000)).toBe('2h');
  });

  it('reads a clock ahead of this browser as "just now", not as a negative', () => {
    // The worker's phone pressed Start; the two clocks disagree by seconds.
    expect(elapsedSince('2026-08-22T08:00:00Z', start - 30_000)).toBe('just now');
  });

  it('has nothing to say about a job that never started', () => {
    expect(elapsedSince(null)).toBeNull();
    expect(elapsedSince('not a date')).toBeNull();
  });
});

describe('the one-way priority raise', () => {
  it('has somewhere to go from Low and Medium and nowhere from High', () => {
    expect(canRaisePriority('Low')).toBe(true);
    expect(canRaisePriority('Medium')).toBe(true);
    expect(canRaisePriority('high')).toBe(false);
  });

  it('names the next step, and it is one step', () => {
    expect(nextPriority('Low')).toBe('Medium');
    expect(nextPriority('Medium')).toBe('High');
  });

  it('explains the refusal instead of hiding the button', () => {
    expect(raisePriorityBlockedReason('Medium')).toBeNull();
    expect(raisePriorityBlockedReason('High')).toMatch(/already High/);
  });
});

describe('timelineEntries', () => {
  it('reads the snake_case rows the staff detail actually sends', () => {
    const [entry] = timelineEntries([{
      id: 'event-1',
      event_type: 'status_changed',
      payload: { from: 'open', to: 'acknowledged' },
      created_at: '2026-08-22T09:00:00Z',
      message: 'Status changed from Pending to In Progress.',
      actor_name: 'Ravi Kumar',
    }]);
    expect(entry).toMatchObject({
      id: 'event-1',
      label: 'Status changed',
      message: 'Status changed from Pending to In Progress.',
      actorName: 'Ravi Kumar',
      createdAt: '2026-08-22T09:00:00Z',
      internal: false,
    });
  });

  it('marks an internal note as internal — that flag is the whole feature', () => {
    const [entry] = timelineEntries([{
      id: 'event-2',
      event_type: 'note_added',
      payload: { note: 'Riser is the real problem.', internal: true },
      created_at: '2026-08-22T09:05:00Z',
      message: 'Riser is the real problem.',
    }]);
    expect(entry.internal).toBe(true);
    expect(entry.label).toBe('Internal note');
  });

  it('does not mark the admin’s resident-visible note as internal', () => {
    const [entry] = timelineEntries([{
      id: 'event-3', event_type: 'note_added', payload: { note: 'Plumber on the way.' },
      message: 'Plumber on the way.',
    }]);
    expect(entry.internal).toBe(false);
  });

  it('writes the sentence itself when the server has no rendering for the new event word', () => {
    // `priority_changed` ships with this amendment; a backend that predates the
    // renderer answers an empty `message`, and a timeline line with no sentence
    // on it is worse than one this file wrote.
    const [entry] = timelineEntries([{
      id: 'event-4', event_type: 'priority_changed', payload: { from: 'low', to: 'medium' },
      message: '',
    }]);
    expect(entry.label).toBe('Priority raised');
    expect(entry.message).toBe('The department raised the priority to Medium.');
  });

  it('renders an event word it has never heard readably rather than blank', () => {
    const [entry] = timelineEntries([{ id: 'e', event_type: 'some_new_word', payload: {} }]);
    expect(entry.label).toBe('some new word');
  });

  it('keeps the server’s order and survives a missing list', () => {
    const rows = [{ id: 'a', event_type: 'raised' }, { id: 'b', event_type: 'taken_up' }];
    expect(timelineEntries(rows).map((row) => row.id)).toEqual(['a', 'b']);
    expect(timelineEntries(undefined)).toEqual([]);
  });
});

describe('staffComplaintFields', () => {
  it('reads the database row the RPC hands back whole', () => {
    expect(staffComplaintFields({
      id: 'complaint-1',
      title: 'Sewage backing up',
      description: 'Twice this week.',
      category: 'Plumbing',
      priority: 'high',
      status: 'open',
      location: 'Basement',
      created_at: '2026-08-22T05:00:00Z',
      expected_resolution_at: '2026-08-23T05:00:00Z',
      taken_up_at: '2026-08-22T06:00:00Z',
      reopened_count: 2,
    })).toMatchObject({
      title: 'Sewage backing up',
      priority: 'high',
      status: 'open',
      createdAt: '2026-08-22T05:00:00Z',
      dueAt: '2026-08-23T05:00:00Z',
      takenUpAt: '2026-08-22T06:00:00Z',
      reopenedCount: 2,
    });
  });

  it('invents nothing when the row is absent', () => {
    const fields = staffComplaintFields(undefined);
    expect(fields.title).toBe('');
    expect(fields.createdAt).toBeNull();
    expect(fields.reopenedCount).toBe(0);
  });
});
