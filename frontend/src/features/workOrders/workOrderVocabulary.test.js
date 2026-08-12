import { describe, expect, it } from 'vitest';
import {
  WORK_ORDER_STATUSES,
  assignmentLabel,
  permittedActions,
  statusLabel,
  statusTone,
} from './workOrderVocabulary';

// The mapping is the only part of the triage screen worth a test. The rest is
// react-query around eight thin wrappers, and a mock for that would test the
// mock. What can actually be got wrong here is silent and expensive: a control
// drawn on a job the database will refuse teaches a supervisor that the button
// sometimes errors, and a control *withheld* from a job that would have
// accepted it removes the only manual lever a state has before the dispatcher
// exists.

describe('permittedActions', () => {
  it('offers all four verbs on a live job that already has an hour', () => {
    const actions = permittedActions({
      status: 'scheduled',
      scheduledStartAt: '2026-08-20T10:00:00Z',
      scheduledEndAt: '2026-08-20T11:00:00Z',
    });
    expect(actions).toEqual({
      edit: true,
      cancel: true,
      assign: true,
      reschedule: true,
      slotRequiredToAssign: false,
    });
  });

  it('still lets a failed visit be edited and called off, but not re-booked or moved', () => {
    // The two sets of "closed" differ, and this is the difference: the answer
    // to a failed visit is a new work order, never a second go at this one.
    const actions = permittedActions({ status: 'failed' });
    expect(actions.edit).toBe(true);
    expect(actions.cancel).toBe(true);
    expect(actions.assign).toBe(false);
    expect(actions.reschedule).toBe(false);
  });

  it('closes every verb on a completed or a cancelled job', () => {
    for (const status of ['completed', 'cancelled']) {
      const actions = permittedActions({ status });
      expect(actions.edit).toBe(false);
      expect(actions.cancel).toBe(false);
      expect(actions.assign).toBe(false);
      expect(actions.reschedule).toBe(false);
    }
  });

  it('demands an hour with the assignment when the job has none', () => {
    const draft = permittedActions({ status: 'draft' });
    expect(draft.assign).toBe(true);
    expect(draft.slotRequiredToAssign).toBe(true);
  });

  it('counts half a slot as no slot, the way the RPC coalesces it', () => {
    const half = permittedActions({
      status: 'offered',
      scheduledStartAt: '2026-08-20T10:00:00Z',
      scheduledEndAt: null,
    });
    expect(half.slotRequiredToAssign).toBe(true);
  });

  it('treats an unknown or absent status as live rather than closed', () => {
    // Three statuses are declared and not yet written by anything, and the
    // worker's verbs are the next step. Defaulting to "closed" would hide the
    // manual lever the moment a new word appears.
    expect(permittedActions({}).edit).toBe(true);
    expect(permittedActions(null).cancel).toBe(true);
  });
});

describe('statusLabel', () => {
  it('gives every declared status a sentence rather than an identifier', () => {
    for (const status of WORK_ORDER_STATUSES) {
      expect(statusLabel(status)).not.toBe(status);
      expect(statusLabel(status).length).toBeGreaterThan(0);
    }
  });

  it('renders a word it has never seen instead of dropping it', () => {
    expect(statusLabel('some_new_state')).toBe('some new state');
    expect(statusLabel(null)).toBe('Unknown');
  });

  it('has a tone for every declared status', () => {
    for (const status of WORK_ORDER_STATUSES) {
      expect(statusTone(status)).toContain('text-');
    }
  });
});

describe('assignmentLabel', () => {
  it('keeps the assignment vocabulary separate from the job one', () => {
    // `withdrawn` belongs to an offer, never to a job: putting somebody else on
    // the work withdraws the previous acceptance and leaves the job untouched.
    expect(assignmentLabel('accepted')).toBe('holds it');
    expect(assignmentLabel('withdrawn')).toBe('withdrawn');
    expect(WORK_ORDER_STATUSES).not.toContain('withdrawn');
  });
});
