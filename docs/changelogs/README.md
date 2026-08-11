# Changelogs

One file per **execution** — a stretch of work planned and delivered as a unit — named
`YYYY-MM-DD-short-slug.md`.

These exist to be **shared with teammates**. Everything else in `docs/` is written for whoever picks
the code up next; these are written for the four other people working on this repo *this week*, who
need to know what changed under them before their next pull.

| | |
|---|---|
| **Sibling** | [`docs/CHANGE_LOG.md`](../CHANGE_LOG.md) — the terse per-session log of *why every `docs/` artifact changed*. Still written. This folder does not replace it. |
| **Sibling** | [`docs/issue fixes/`](../issue%20fixes/README.md) — one file per fixed GitHub issue |
| **Sibling** | [`docs/potential issues/`](../potential%20issues/README.md) — problems found but not fixed |

---

## The difference from `CHANGE_LOG.md`

`CHANGE_LOG.md` answers *"why does this document say that?"* — one entry per session, terse, keyed
on documents, tagged `PO` / `DERIVED` / `AUDIT`.

A changelog here answers *"what do I need to know before I pull?"* — keyed on **endpoints, schema
and contracts**, grouped so a teammate can find their own files without reading the rest.

## What each one contains

Written **as each phase lands**, never reconstructed at the end. A changelog assembled from memory
after eight phases is a summary; the details a teammate needs are exactly the ones that get lost.

Per phase:

- **What changed and why** — prose, not a restated diff.
- **Endpoints** — new, changed and removed, with method, path, guard, and whether it is additive or
  breaking.
- **Schema** — new tables and columns, changed constraints, RPCs added, each named with its
  migration file.
- **Contract changes that break somebody** — under their own heading. These are the only lines
  another person *has* to read.
- **Files touched, grouped by owner** — several screens in this repo have a clear author; each
  person should find their own files in one place rather than scanning a flat list.
- **What to do after pulling.**
- **Open questions raised, not answered.**

---

| File | Covers |
|---|---|
| [2026-08-11 — departments, skills, manager provisioning, connectivity](2026-08-11-departments-skills-and-connectivity.md) | The four instructions in `further instructions.md`: the admin department form, the department-manager portal, global skills with fuzzy matching, and wiring every dangling backend operation. |
