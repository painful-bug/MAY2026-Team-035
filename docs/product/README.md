# Product inputs — Team 035

The requirements the team gathered, kept in the repo so the backend can be traced back to them.

| File | What it is |
|---|---|
| [`USER_IDENTIFICATION.md`](USER_IDENTIFICATION.md) | The three user tiers and who is in each |
| [`USER_STORIES.md`](USER_STORIES.md) | 24 user stories with the interview pain points behind them |

**These two files are the team's work, reproduced verbatim.** They are transcribed from
`user-identification.txt` and `user-stories.txt` with markdown headings and stable `US-*` /
`UT-*` identifiers added — no wording changed, nothing dropped, nothing invented. If the team
revises the originals, replace these rather than editing them in place, so a reader can never be
looking at a version the team does not recognise.

**Why they are here.** A user story that lives in a document nobody opens cannot be checked against
the code. Kept alongside the design docs, they are checkable: [`../API.md` §16](../API.md#16-user-stories--endpoints)
maps every endpoint we have built to the story it serves, and names the stories nothing serves yet.
That second half is the useful half — it is the difference between "we built a backend" and "we
built the backend these users asked for, minus these seven things, on purpose".

**Standing rule.** When an endpoint is added, changed or removed, update the traceability matrix in
`API.md` §16 in the same commit — **and the per-story `Backend:` line in
[`USER_STORIES.md`](USER_STORIES.md), which is an index of that matrix and drifts silently when it is
not.** A matrix that is 80% current is worse than none, because it is believed.

The drift is now checked rather than remembered:
`cd backend && python scripts/api_map_scan.py` compares the verdict in three places — this document,
`API.md` §16, and `x-user-stories` in the generated spec — and reports any disagreement.

## Scope caveat, stated once so it is not restated in every row

This branch builds the **admin dashboard** backend only. That is not a coverage failure against the
stories below — it is the agreed scope. The resident mobile surface (push notifications, the
one-tap widget, visitor pre-approval) and the security-gate surface (digital registers, tanker log,
offline verification) are whole workstreams that nobody has started. §14 says so per story rather
than leaving a reader to infer it from silence.
