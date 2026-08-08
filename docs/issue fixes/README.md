# Issue fixes

One file per fixed GitHub issue, named after the issue number: `22.md` is issue #22.

Each one answers the question a git log cannot: **why is the code like this?** A commit tells you
what changed. These tell you what was broken, what we found while looking, what we chose, and — most
usefully — **what we nearly did instead and why that would have been wrong**.

They are written for someone who was not in the room. No prior context assumed.

| | |
|---|---|
| **Sibling folder** | [`docs/potential issues/`](../potential%20issues/README.md) — problems found but *not* fixed, written to be raised as new issues |
| **Related** | [`docs/CHANGE_LOG.md`](../CHANGE_LOG.md) — the reason behind every change to a `docs/` artifact |

---

## How to read one

**Start at the top table, stop when you have what you came for.** They are written so that each
section is worth reading on its own — you should never have to read the whole thing to get an answer.

| If you want to know… | Read |
|---|---|
| What was broken, in one line | The **short version** table |
| Whether this affects you right now | **What still needs a human** — outstanding work no commit can do |
| Why the code looks the way it does | **Where the fix went**, and the numbered decisions under it |
| Why the obvious fix is not what's there | **The trap we nearly walked into** |
| What files moved | **Everything that changed** |
| How to prove it still works | **How to check this yourself** |

Two conventions worth knowing:

- **Code blocks are labelled `# before` and `# after`.** A `# DON'T` block is a fix that was
  considered and rejected — it is in the document precisely because it looks correct.
- **"What still needs a human" is not a nicety.** If a fix depends on a dashboard setting, a
  migration someone has to run, or a decision another owner has to make, it is listed there and the
  document's status line at the top says the fix is incomplete. Check that section before assuming
  an issue is closed.

---

## How to write one

Copy the structure below. It is not a form to fill in — drop any section that has nothing true to
say in it, because an empty heading costs the reader more than a missing one.

### The structure

```markdown
# Issue #<n> — <the issue title, verbatim>

| | |
|---|---|
| **Issue** | link |
| **Reported by** | who, when |
| **Fixed by** | who, when |
| **Branch** | issues/<n>-<short-topic> |
| **Commits** | the short SHAs |
| **Status** | done, or done-except-<the outstanding thing> |

## The short version
A table: what was reported | what was actually wrong | where the fix lives.
One row per distinct bug. Say plainly which one is the serious one.

## Bug A — <what it actually was, not what was reported>
### What was happening      — the before code, and why it was wrong
### The trap we nearly walked into  — the wrong fix, and what stopped us
### Where the fix went      — the after code, and the decisions inside it
### <anything found next door>      — latent bugs the investigation turned up

## Bug B — …

## Everything that changed
Tables by area: backend, frontend, tests (name every new test), docs.

## What we deliberately did not do
Each with its reason. This section prevents the same argument next quarter.

## What still needs a human
Numbered, actionable, with the exact path or dashboard location. Plus how to verify.

## How to check this yourself
The command to run, and the evidence numbers at the time of the fix.

## Related findings
Point at docs/potential issues/ for anything found but not fixed.
```

### The rules that actually matter

**1. Name the bug that existed, not the bug that was reported.** Issue #22 was filed as one bug and
was two, with unrelated causes. If the title on GitHub is misleading, the document says so in its
first table. The reporter is not being corrected; the reader is being saved.

**2. Write down the fix you rejected.** This is the highest-value paragraph in any of these
documents. If a wrong fix looked obviously right to you, it will look obviously right to the next
person — who will then "improve" your code back into the bug. Name what stopped you: the ruling in a
doc, the test that fails, the flow it would break.

**3. Explain *why* each decision, not just what.** "We converged both error paths on one code"
is a fact. "…so the behaviour stops depending on a dashboard toggle no file in this repo can see" is
the reason someone needs before they touch it.

**4. Say when a fix is only half in the code.** Configuration, migrations, dashboard settings and
other people's decisions do not live in git. If the real root cause is outside the repository, the
status line at the top must say the fix is incomplete, and **What still needs a human** must give the
exact steps. A document that reads as finished when it isn't is worse than no document.

**5. Record latent bugs you found but did not chase.** A field that has silently been the wrong value
since it was written is worth a subsection even if nothing reads it today — the point is that the
next person to build on it needs to know.

**6. Everything checkable must be checked.** Every claim names the file it came from. Every count
(tests, lint violations) is a number someone can reproduce with the command given. Never write
"tests pass" without the before-and-after figures.

**7. Reader-friendly beats complete.** Short paragraphs, tables over prose lists, bold for the one
sentence per section that matters. A mermaid `flowchart TD` is worth writing when a bug is a *chain*
of causes — it turns five paragraphs into one glance.

### Housekeeping

- **Branch naming:** `issues/<number>-<short-topic>`, e.g. `issues/22-email-verification`. The number
  is what a reader looks up; two or three words of topic are enough beside it.
- **Log it.** Add a block to [`docs/CHANGE_LOG.md`](../CHANGE_LOG.md) for any `docs/` artifact the
  fix changed, with the reason.
- **Split the findings out.** Things found while investigating that are *not* this issue go to
  [`docs/potential issues/`](../potential%20issues/README.md), written ready to paste into a new
  GitHub issue. Link to them from the fix document's last section; do not smuggle them into the fix.

---

## Index

| Issue | Title | Status |
|---|---|---|
| [#22](22.md) | Email verification link button is disabled, and unverified accounts can log in | Code fixed. **Supabase email template change still outstanding** |
