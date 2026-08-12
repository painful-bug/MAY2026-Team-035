import { describe, expect, it } from 'vitest';
import { canCancelUnstartedWork, projectTracker } from './trackerProjection';

describe('projectTracker', () => {
  it('projects the job lifecycle without inventing a close', () => {
    const tracker = projectTracker([
      { type: 'raised' }, { type: 'job_assigned', payload: { assigneeName: 'Ravi' } },
      { type: 'job_scheduled' }, { type: 'job_started' }, { type: 'job_completed' },
    ]);
    expect(tracker.nodes.map((node) => node.state)).toEqual(['done', 'done', 'done', 'done', 'done', 'pending']);
    expect(tracker.nodes[1].detail).toContain('Ravi');
  });

  it('restarts after reopen and keeps the annotation', () => {
    const tracker = projectTracker([{ type: 'job_completed' }, { type: 'reopened' }, { type: 'raised' }]);
    expect(tracker.nodes[4].state).toBe('pending');
    expect(tracker.annotations[0].label).toBe('Reopened');
  });

  it('allows cancellation for a new assignment after an earlier visit started', () => {
    expect(canCancelUnstartedWork([
      { type: 'job_assigned' }, { type: 'job_started' }, { type: 'job_failed' },
      { type: 'job_assigned' },
    ])).toBe(true);
  });
});
