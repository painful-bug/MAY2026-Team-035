-- ---------------------------------------------------------------------------
-- 20260821170000_blocked_invitee_notice.sql
--
-- The person whose leadership invitation was refused is told why.
--
-- THE GAP, IN ONE SENTENCE
--
-- `20260821140000_leadership_exclusivity.sql` section 5 made a blocked claim
-- *survivable* -- the invitation is skipped rather than raised, stays `pending`,
-- gains a `blocked_reason`, and the inviting department is sent one
-- `staff_invitation.blocked` notification on the `blocked_at is null` edge. Every
-- one of those is addressed to the department. The **invitee** is told nothing at
-- all: they sign in with the address that was typed for them, the invitation
-- silently does not take, and they land in whatever portal their own identity
-- already entitled them to -- with no way to connect that to the manager who told
-- them last week that their account was ready.
--
-- The product owner's ruling, 2026-08-21: the invitee must be told, on the same
-- edge, in wording that says what happened and what -- if anything -- they can do
-- about it. That wording is frozen and is reproduced verbatim in section 1.
--
-- WHY THIS IS A WHOLE COPY OF `claim_staff_invitations`
--
-- House convention, `20260812113000` section 1: a migration that changes a
-- function another migration owns copies the body forward whole and marks every
-- changed region with a `-- CHANGED:` comment. The body below was extracted
-- mechanically from `20260821140000` section 5 (lines 781-941 of that file), so
-- the starting point is provably the text that was applied to the hosted database
-- on 2026-08-21. Its own `-- CHANGED` markers -- the ones the leadership file
-- added to `20260812090200`'s original -- are left exactly where they are, and the
-- three regions this file adds are marked `-- CHANGED (20260821170000)` so a
-- reader can tell the two generations apart.
--
-- EVERY PROPERTY OF THE COPY THAT MUST NOT MOVE, AND DOES NOT
--
--   * the loop body contains **zero** `raise exception`. This function runs
--     inside `resolve_session` on every membership-less session read and
--     `auth_service._claim_staff_invitations` swallows what it raises, so a
--     refusal spelled as an exception would abandon every *other* pending
--     invitation in the same call, silently. `notify_profile` cannot raise for
--     the arguments used here: its two guards are a null profile (impossible --
--     the function returns early on a null `p_profile_id`) and a blank kind (a
--     literal).
--   * a blocked invitation stays `status = 'pending'`; both admin verbs still
--     apply to it.
--   * `blocked_reason` / `blocked_at` are written exactly as before, and
--     `blocked_at` still uses `coalesce` so it records the *first* refusal.
--   * the department notification still fires once, on the same edge.
--   * an invitation that finally lands still clears `blocked_reason`/`blocked_at`.
--   * `order by s.created_at` -- older invitation wins -- is untouched, which is
--     what makes "invited to two communities, one takes and the other is
--     refused" come out the way ruling 2 describes.
--
-- WHY `notify_profile` AND NOT `notify_member`
--
-- The recipient may hold no membership at all. In the marketplace case they are a
-- registered provider who has been hired nowhere; in the already-leads case they
-- hold a membership in a *different* community, and addressing a notification to
-- it would file this message under that community's heading -- and
-- `20260821140000` section 8's `notifications_read_own` policy would then hide it
-- the day that membership ends. `notify_profile` (`0041` section 2) files a
-- person-scoped, community-less row, which `membership_is_live(null)` deliberately
-- keeps readable forever. It is the same writer `0041` used for the two hiring
-- messages whose recipients hold no membership, and for the same reason.
--
-- NOTHING ELSE IN THIS FILE
--
-- No column, no table, no policy, no trigger, no grant change. One function is
-- redeclared and one `do` block counts what this file cannot reach.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. The frozen wording
--
-- Approved by the product owner on 2026-08-21 and reproduced here so that a
-- reader of the SQL sees the sentences rather than a reference to them. `{}` is
-- the community's name, substituted at write time.
--
--   provider case
--     "Your invitation to join {community} couldn't be applied. This account is
--      registered as a marketplace service professional, and department
--      leadership can't be combined with a provider profile. Ask the community to
--      invite a different email address."
--
--   already-leads case
--     "Your invitation to join {community} couldn't be applied because you
--      already manage or supervise another community. Leadership is held in one
--      community at a time -- once your current engagement ends, the invitation
--      can be applied on your next sign-in."
--
-- THE FROZEN TEXT IS THE `body`, WHOLE AND UNSPLIT.
--
-- `notifications_service.render` reads exactly three payload keys -- `title`,
-- `body`, `url` -- and both transports (the feed row and the Web Push line) use
-- the same two strings. Splitting the approved sentences across `title` and
-- `body` would make the wording depend on which surface reassembled it, and on
-- the already-leads sentence there is no clause boundary to split at without
-- rewriting the join. So `body` carries the approved text uninterrupted and
-- `title` is a five-word subject line, which is not product copy.
--
-- Plain text, not Markdown: `NotificationBell.jsx` renders `title` and `body` as
-- JSX text nodes and `push_service` puts them on a lock screen. Emphasis marks
-- would arrive as literal asterisks on both.
--
-- THE EVENT TYPE AND THE PAYLOAD
--
-- `staff_invitation.not_applied`. Dotted, in the `staff_invitation.` namespace
-- the department-side `staff_invitation.blocked` already opened -- these two are
-- the same event told to two audiences, and a reader of `pg_stat` or of the feed
-- should be able to see that from the kind alone. A *separate* kind rather than a
-- second `staff_invitation.blocked` row, because the two carry opposite voices
-- ("they could not be admitted" against "your invitation couldn't be applied"),
-- and one kind that renders as either sentence is one kind whose fallback title
-- is wrong for half its readers.
--
-- The payload mirrors the department side's shape -- the rendered strings, the
-- invitation id, and the id and name of the thing the sentence names. The
-- department's row names the department because its `url` routes there; this one
-- names the community because that is what the invitee's sentence is about.
--
-- NO `url`, DELIBERATELY.
--
-- There is no screen for this. The invitee is not a member of that community and
-- never becomes one; nothing in any portal lists invitations addressed to you,
-- and the two blocked populations land in different portals anyway (the provider
-- in `/worker`, the sitting leader in `/manager` or `/security-manager`). The
-- house rule is `notifications_service._FALLBACK_URLS`' own docstring -- "a guess
-- about where a notification should land is a worse failure than no link, because
-- a link that goes to the wrong screen is one the reader believes" -- and the
-- precedent is that `render` returns `""` for a payload with no `url` and
-- `NotificationBell.openItem` then marks the row read and navigates nowhere. The
-- message is the whole content; there is nothing to click through to.
-- ---------------------------------------------------------------------------

-- `claim_staff_invitations` from `20260821140000` 5, copied whole, which copied
-- it whole from `20260812090200` 4. Everything the header of that section says
-- about it still holds: idempotent, no auth check because the verified email IS
-- the authorization, and execute revoked from `authenticated`.
create or replace function public.claim_staff_invitations(
  p_profile_id uuid,
  p_email      text
)
returns table (
  membership_id uuid,
  community_id  uuid,
  department_id uuid,
  role          text,
  rank          text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email citext := lower(btrim(coalesce(p_email, '')))::citext;
  v_row   record;
  v_kind  text;
  v_role  text;
  v_membership uuid;
  v_block text;      -- CHANGED
  v_department text; -- CHANGED
  v_reason text;     -- CHANGED (20260821170000): which ruling refused this one
  v_community text;  -- CHANGED (20260821170000): the name the invitee's sentence uses
begin
  if p_profile_id is null or v_email = '' then
    return;
  end if;

  for v_row in
    select s.*
      from public.staff_invitations s
     where s.invitee_email = v_email
       and s.status = 'pending'
     order by s.created_at
  loop
    select d.kind into v_kind
      from public.departments d
     where d.id = v_row.department_id;

    -- Already a member of that community: leave the invitation pending rather
    -- than claiming it into a membership that cannot be created. An admin
    -- looking at the department sees it still outstanding, which is true.
    if exists (
      select 1 from public.community_memberships m
       where m.community_id = v_row.community_id
         and m.profile_id = p_profile_id
         and m.status = 'active'
         and m.ended_at is null
    ) then
      continue;
    end if;

    -- CHANGED: rulings 1 and 2, skipped rather than raised. See section 5's
    -- header for why an exception here would abandon the whole claim silently.
    --
    -- Re-asked per iteration on purpose: this loop is the one place two
    -- leadership postings can be created in one statement, and the second one
    -- must see the first. The insert below is visible to this read within the
    -- transaction, so an email invited to two communities takes the older
    -- invitation -- `order by s.created_at` -- and is blocked on the newer,
    -- which is the outcome ruling 2 describes.
    v_block := null;
    -- CHANGED (20260821170000): reset beside `v_block`, or the second iteration
    -- of a two-invitation loop would inherit the first one's reason.
    v_reason := null;

    if exists (select 1 from public.service_providers
                where profile_id = p_profile_id) then
      v_reason := 'marketplace';  -- CHANGED (20260821170000)
      v_block :=
        'They signed in with an account that is registered as a marketplace service professional. Leadership is invite-only and is never held by a registered provider, so this invitation was not applied.';
    elsif public.active_leadership_community(p_profile_id) is not null then
      v_reason := 'elsewhere';    -- CHANGED (20260821170000)
      v_block :=
        'They signed in, but already manage or supervise another community. Leadership is held in one community at a time, so this invitation was not applied.';
    end if;

    if v_block is not null then
      -- The notification fires on the transition only. This function runs on
      -- every membership-less session read, and a blocked person keeps signing
      -- in.
      if v_row.blocked_at is null then
        select d.name into v_department
          from public.departments d where d.id = v_row.department_id;

        -- CHANGED (20260821170000): the invitee's sentence names the community,
        -- not the department -- they were never admitted to the department and
        -- the community is the name they were given.
        select c.name into v_community
          from public.communities c where c.id = v_row.community_id;

        perform public.notify_department_leadership(
          v_row.department_id, 'staff_invitation.blocked',
          jsonb_build_object(
            'title', coalesce(v_row.invitee_name, 'Someone')
                     || ' could not be admitted',
            'body', v_block,
            'url', '/admin/departments/' || v_row.department_id::text,
            'invitationId', v_row.id,
            'departmentId', v_row.department_id,
            'departmentName', v_department));

        -- CHANGED (20260821170000): and so is the invitee, on the same edge and
        -- inside the same guard, so the two can never disagree about whether
        -- this refusal has already been announced. Person-scoped and
        -- community-less by design -- see this file's header.
        perform public.notify_profile(
          p_profile_id, 'staff_invitation.not_applied',
          jsonb_build_object(
            'title', 'Your invitation couldn''t be applied',
            'body',
              case v_reason
                when 'marketplace' then
                  'Your invitation to join '
                  || coalesce(v_community, 'the community')
                  || ' couldn''t be applied. This account is registered as a marketplace service professional, and department leadership can''t be combined with a provider profile. Ask the community to invite a different email address.'
                else
                  'Your invitation to join '
                  || coalesce(v_community, 'the community')
                  || ' couldn''t be applied because you already manage or supervise another community. Leadership is held in one community at a time — once your current engagement ends, the invitation can be applied on your next sign-in.'
              end,
            'invitationId', v_row.id,
            'communityId', v_row.community_id,
            'communityName', v_community));
      end if;

      update public.staff_invitations
         set blocked_reason = v_block,
             blocked_at     = coalesce(blocked_at, now()),
             updated_at     = now()
       where id = v_row.id;

      continue;
    end if;

    -- Derived, never stored -- see `20260812090200`'s header table.
    if v_row.rank = 'manager' then
      v_role := 'manager';
    elsif v_kind = 'security' then
      v_role := 'security';
    else
      v_role := 'worker';
    end if;

    insert into public.community_memberships (
      community_id, profile_id, department_id, role, status, joined_at
    )
    values (
      v_row.community_id, p_profile_id, v_row.department_id,
      v_role::public.membership_role, 'active', now()
    )
    returning id into v_membership;

    insert into public.staff_assignments (
      community_id, department_id, membership_id, display_name, phone_e164,
      job_title, rank, status, employment_type, started_at
    )
    values (
      v_row.community_id, v_row.department_id, v_membership,
      v_row.invitee_name, v_row.invitee_phone_e164, v_row.job_title,
      v_row.rank, 'active', 'staff', current_date
    );

    update public.staff_invitations
       set status = 'claimed',
           claimed_by_profile_id = p_profile_id,
           claimed_at = now(),
           -- CHANGED: an invitation that finally landed is not blocked.
           blocked_reason = null,
           blocked_at = null,
           updated_at = now()
     where id = v_row.id;

    membership_id := v_membership;
    community_id  := v_row.community_id;
    department_id := v_row.department_id;
    role          := v_role;
    rank          := v_row.rank;
    return next;
  end loop;
end;
$$;

comment on function public.claim_staff_invitations(uuid, text) is
  'Turn every pending invitation for this verified email into a membership and '
  'a roster row. Called by resolve_session on a profile with no membership. '
  'Idempotent. Service role only -- the email IS the authorization, so a '
  'caller who could choose it could admit themselves. An invitation the '
  '2026-08-21 exclusivity rulings refuse is skipped and marked with a '
  'blocked_reason, never raised: this runs inside a session read whose caller '
  'swallows exceptions, so raising would abandon every other invitation too. '
  'On that same first refusal BOTH sides are told -- the department by '
  'notify_department_leadership, and the invitee by notify_profile, because '
  'somebody who signs in and finds nothing happened is owed the reason.';

revoke all on function public.claim_staff_invitations(uuid, text)
  from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- 2. What this file cannot reach, counted rather than repaired
--
-- `20260821140000` section 9's argument, applied to a smaller question. The
-- notification is guarded by `blocked_at is null`, which is the edge and is
-- correct: a blocked person keeps signing in, and a message re-sent on every
-- session read is a message nobody reads. The cost is that an invitation blocked
-- *before* this file was applied has already crossed that edge, so its invitee is
-- never told retroactively.
--
-- Nothing here fixes that, and the fix is not a migration's to make: sending the
-- notice for those rows would mean writing `blocked_at` backwards or bypassing the
-- guard, and either would re-notify anybody the department has since re-invited.
-- The department's own remedy already re-arms the edge -- `update_staff_invitation`
-- clears `blocked_reason`/`blocked_at`, so correcting or re-issuing the address
-- makes the next sign-in announce itself normally.
--
-- Expected to be zero: the columns were added on 2026-08-21 and this file follows
-- the same day.
-- ---------------------------------------------------------------------------

do $$
declare
  v_already_blocked integer;
begin
  select count(*) into v_already_blocked
    from public.staff_invitations s
   where s.blocked_at is not null
     and s.status = 'pending';

  if v_already_blocked > 0 then
    raise notice
      'blocked invitee notice: % pending invitation(s) were already marked blocked before this file was applied. Their invitees crossed the notification edge without one and are not told retroactively. Correcting or re-issuing the address (update_staff_invitation clears blocked_reason and blocked_at) re-arms it for the next sign-in.',
      v_already_blocked;
  end if;
end;
$$;


-- ---------------------------------------------------------------------------
-- 3. Post-apply verification
--
-- Run these in the SQL Editor after this file. They are also reproduced in
-- `docs/plans/MIGRATION_APPLY_RUNBOOK.md` 15. Nothing below runs as part of the
-- migration; the block in section 2 is the only thing that executes.
--
--   -- (a) Exactly one claim_staff_invitations, and it is this one.
--   select count(*) as definitions,
--          bool_or(prosrc like '%staff_invitation.not_applied%') as tells_invitee,
--          bool_or(prosrc like '%staff_invitation.blocked%')     as tells_department
--     from pg_proc
--    where pronamespace = 'public'::regnamespace
--      and proname = 'claim_staff_invitations';
--   -- expect: definitions = 1, both booleans true.
--
--   -- (b) The refusal is still a skip. Zero `raise` anywhere in the body.
--   select prosrc ~* '\mraise\M' as raises
--     from pg_proc
--    where pronamespace = 'public'::regnamespace
--      and proname = 'claim_staff_invitations';
--   -- expect: false.
--
--   -- (c) Both notifications sit inside the same `blocked_at is null` guard.
--   select prosrc like '%if v_row.blocked_at is null then%' as guarded
--     from pg_proc
--    where pronamespace = 'public'::regnamespace
--      and proname = 'claim_staff_invitations';
--   -- expect: true.
--
--   -- (d) The invitee's rows are person-scoped and community-less, so the
--   --     ruling-3 feed policy keeps them readable forever.
--   select count(*)                                        as rows_written,
--          count(*) filter (where recipient_profile_id is null)    as unaddressed,
--          count(*) filter (where recipient_membership_id is not null) as scoped
--     from public.notifications
--    where kind = 'staff_invitation.not_applied';
--   -- expect: unaddressed = 0 and scoped = 0, whatever rows_written is.
-- ---------------------------------------------------------------------------
