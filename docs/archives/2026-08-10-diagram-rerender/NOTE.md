# Archived diagram renders — replaced 2026-08-11

These are the rendered images that were current in the repo before the
service-operations re-render. Each was replaced because its **source file had
moved on** and an image that silently disagrees with its source is worse than
no image. The sources themselves (`.puml`, `.dbml`) were never stale — only
these projections of them. Nothing here is a source of truth; keep for
provenance and before/after comparison only.

## What is in this folder

| File | Was rendered from | Why it was replaced |
|---|---|---|
| `HomeBandhu-Domain-Model.svg` | `docs/class-diagram/homebandhu-domain.puml` | Rendered before the Phase 1/2 service-operations work. Missing everything migrations `0034`–`0046` added to the source: the Service Personnel package (`ServiceProvider`, `ServiceApplication`, `StaffDeparture`, `Conversation`, `DispatchTask`, the gate classes), the departure-scheduling dates (`requestedEffectiveAt`/`effectiveAt`), the `DEPARTURE_REMOVAL` dispatch kind, the queue-priority attribute, and the Direct Messages classes (`DirectMessageThread`, `DirectMessage`, `DmThreadKind`). |
| `HomeBandhu-Domain-Model.png` | same `.puml` | Same staleness — **plus this PNG was silently truncated**: PlantUML clips PNG output at 4096×4096 by default and this file is exactly 4096×4096 while the full diagram is ~21500 px wide. The right-hand ~80 % of the diagram was never in the committed PNG. The replacement was rendered with `-DPLANTUML_LIMIT_SIZE=24576` and is complete (21474×5395). |
| `erd.png` | `docs/diagrams/homebandhu_submission_erd.dbml` | A dbdiagram.io export that had fallen far behind its source: it still shows `public.vendors` and `staff_skills` (both dropped by `0044`) and predates every service-operations table — no `service_providers`, `departments` hiring columns, `work_orders` dispatch fields, `dispatch_tasks`, `staff_departures`, security-gate tables, or `dm_threads`/`dm_messages`. |

## How the replacements were made (and one deliberate change of tool)

- **Class diagram** (`docs/class-diagram/HomeBandhu-Domain-Model.svg/.png`):
  same toolchain as before — PlantUML (`1.2024.8`, the last Java-8-compatible
  release; `1.2025.0+` needs Java 11) + Graphviz `dot` (`15.1.1`). Layout style
  is unchanged, only content and the un-truncated PNG differ.
- **ERD** (`docs/diagrams/erd.svg` + `erd.png`): **the tool changed.** The old
  image was a manual dbdiagram.io export; the replacement is generated offline
  by `@softwaretechnik/dbml-renderer` (SVG, plus PNG via its Graphviz `dot`
  output). Offline generation was chosen so the render can be repeated
  mechanically whenever the `.dbml` changes, instead of depending on a by-hand
  paste-and-export that had already let the image drift ~10 migrations behind.
  The visual style therefore differs (Graphviz auto-layout, tall aspect ratio,
  new companion `erd.svg`). The `.dbml` still pastes into dbdiagram.io fine if
  a hand-arranged export is wanted for a submission document.
- While re-rendering, three `note:` strings in the `.dbml` were reworded
  because they contained bare apostrophes inside single-quoted DBML strings —
  a parse error in any strict DBML parser (lines around `work_orders` /
  `work_order_assignments`, wording only, no schema meaning changed).

The re-render and this archive were requested by the product owner on
2026-08-10 ("preserve the old ones in a folder in docs called archives with a
note on what changed and why"). Change is logged in `docs/CHANGE_LOG.md`
(Session 56).
