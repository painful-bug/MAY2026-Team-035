import { describe, expect, it } from 'vitest';
import { portalNotificationUrl } from './portalUrl';

// `portalUrl.js` had no test of its own until 2026-08-21. Its only coverage was
// `backend/tests/test_notification_links.py`, which mirrors this rule table in
// Python and asks the far better question -- does the rewritten path exist in
// `App.jsx`? -- but asks it of the mirror. The mirror is compared with this
// file's source text, not run against it, so a rule could be right in Python,
// spelled the same in JavaScript, and still not fire: an object looked up with
// the wrong key, a `Set` membership inverted, an ordering that lets the
// department-root rule swallow a sub-screen. Those are this file's failure
// modes and they need this file executed.
//
// The cases below are the rule table read out loud. Each one is a notification
// somebody is actually sent, so a broken row here is a click that does nothing.

describe('portalNotificationUrl', () => {
  describe('a service department supervisor (portal `worker`)', () => {
    it('sends a work-order notification to the queue their portal mounts', () => {
      // The five kinds keyed to `work_orders.supervisor_membership_id`. The
      // query string carries the row they were told about, so it has to survive.
      expect(
        portalNotificationUrl('/admin/departments/dep-1/work-orders?job=job-9', 'worker'),
      ).toBe('/worker/departments/dep-1/work-orders?job=job-9');
    });

    it('leaves hiring, staff and candidates links alone — `/worker` mounts none of them', () => {
      // A visible bounce beats a rewrite to a route that does not exist. This
      // is the whole reason the sub-screen list is per-portal rather than
      // shared, and the assertion that fails if somebody flattens it back.
      for (const path of [
        '/admin/departments/dep-1/hiring?tab=roster',
        '/admin/departments/dep-1/staff/staff-2?departure=dep-3',
        '/admin/departments/dep-1/candidates/cand-4',
      ]) {
        expect(portalNotificationUrl(path, 'worker')).toBe(path);
      }
    });

    it('sends a complaint notification to `/worker/complaints`', () => {
      // `notify_complaint_staff` was widened to supervisor-rank roster holders
      // on 2026-08-21; this is where those rows land.
      expect(portalNotificationUrl('/admin/complaints?complaint=c-7', 'worker')).toBe(
        '/worker/complaints?complaint=c-7',
      );
      expect(portalNotificationUrl('/admin/complaints', 'worker')).toBe(
        '/worker/complaints',
      );
    });

    it('sends a hiring conversation to `/worker/messages`', () => {
      expect(portalNotificationUrl('/admin/messages?conversation=x', 'worker')).toBe(
        '/worker/messages?conversation=x',
      );
    });

    it('trades the department root for their own base, deliberately', () => {
      // Reversed later on 2026-08-21, on the product owner's ruling. The first
      // reading left this alone because a worker's base is a jobs dashboard
      // rather than a department overview — true of the screens, and beside the
      // point: `/admin/departments/{id}` is Admin-guarded, so this reader is
      // redirected to `/worker` either way. The choice is between arriving
      // there deliberately and arriving there via a click that did nothing.
      //
      // They are a live audience for it: `notify_department_leadership`
      // (`0043` §419–436) includes supervisor-rank roster holders, and
      // `staff_invitation.blocked` (`20260821170000`) carries this url.
      expect(portalNotificationUrl('/admin/departments/dep-1', 'worker')).toBe('/worker');
      // The query string goes with it, exactly as it does for a manager: the
      // base is a different screen, so carrying a parameter it cannot read
      // would be noise.
      expect(portalNotificationUrl('/admin/departments/dep-1?tab=roster', 'worker')).toBe(
        '/worker',
      );
    });

    it('still lets a sub-screen rule win over the department root', () => {
      // Ordering, which is this file's whole reason for existing: the root
      // pattern is anchored at `[^/?#]+$`, so a work-orders path must never
      // reach it. If it ever did, the five work-order notifications would all
      // land on the jobs dashboard with the job they name thrown away.
      expect(
        portalNotificationUrl('/admin/departments/dep-1/work-orders?job=job-9', 'worker'),
      ).toBe('/worker/departments/dep-1/work-orders?job=job-9');
    });

    it('leaves the screens no portal but `/admin` has', () => {
      for (const path of [
        '/admin/amenities?booking=b-1',
        '/admin/complaint-triage',
        '/admin/security/incidents',
      ]) {
        expect(portalNotificationUrl(path, 'worker')).toBe(path);
      }
    });
  });

  describe('a department manager (unchanged by the 2026-08-21 rewrite)', () => {
    it('still gets all four department sub-screens', () => {
      expect(
        portalNotificationUrl('/admin/departments/d/hiring?tab=departures', 'manager'),
      ).toBe('/manager/departments/d/hiring?tab=departures');
      expect(portalNotificationUrl('/admin/departments/d/staff/s?departure=x', 'manager'))
        .toBe('/manager/departments/d/staff/s?departure=x');
      expect(portalNotificationUrl('/admin/departments/d/candidates/c', 'manager')).toBe(
        '/manager/departments/d/candidates/c',
      );
      expect(portalNotificationUrl('/admin/departments/d/work-orders?job=j', 'manager'))
        .toBe('/manager/departments/d/work-orders?job=j');
    });

    it('still trades the department root for their own base', () => {
      expect(portalNotificationUrl('/admin/departments/d', 'manager')).toBe('/manager');
    });

    it('still gets complaints and messages, and still not incidents', () => {
      expect(portalNotificationUrl('/admin/complaints?complaint=c', 'manager')).toBe(
        '/manager/complaints?complaint=c',
      );
      expect(portalNotificationUrl('/admin/messages?conversation=x', 'manager')).toBe(
        '/manager/messages?conversation=x',
      );
      // `0040` no longer reaches a plumbing manager, and there is no screen for
      // it here if a pre-correction row does.
      expect(portalNotificationUrl('/admin/security/incidents', 'manager')).toBe(
        '/admin/security/incidents',
      );
    });
  });

  describe('a security manager (unchanged by the 2026-08-21 rewrite)', () => {
    it('still gets the incidents screen at its own mount', () => {
      expect(portalNotificationUrl('/admin/security/incidents', 'security-manager')).toBe(
        '/security-manager/incidents',
      );
    });

    it('still gets the department sub-screens and the root', () => {
      expect(
        portalNotificationUrl('/admin/departments/d/work-orders?job=j', 'security-manager'),
      ).toBe('/security-manager/departments/d/work-orders?job=j');
      expect(portalNotificationUrl('/admin/departments/d', 'security-manager')).toBe(
        '/security-manager',
      );
    });

    it('is still kept away from complaints, which that portal does not mount', () => {
      // A gate department's work arrives as incidents and shift entries. Adding
      // `worker` to the complaints list must not have swept this one along.
      expect(portalNotificationUrl('/admin/complaints?complaint=c', 'security-manager'))
        .toBe('/admin/complaints?complaint=c');
    });
  });

  describe('everything the table has no answer for', () => {
    it('passes a url through untouched when the portal is not in the table', () => {
      for (const portal of ['admin', 'resident', 'security', undefined, null, '']) {
        expect(portalNotificationUrl('/admin/complaints?complaint=c', portal)).toBe(
          '/admin/complaints?complaint=c',
        );
      }
    });

    it('passes through anything that is not an admin url', () => {
      for (const path of ['/worker/messages?conversation=x', '/resident/complaints', '/']) {
        expect(portalNotificationUrl(path, 'worker')).toBe(path);
      }
    });

    it('passes through an empty url rather than throwing', () => {
      // `NotificationBell` reads `item.url` straight off the row, and a row
      // with none is a notification with no link rather than a crash.
      expect(portalNotificationUrl('', 'worker')).toBe('');
      expect(portalNotificationUrl(null, 'worker')).toBe(null);
      expect(portalNotificationUrl(undefined, 'worker')).toBe(undefined);
    });
  });
});
