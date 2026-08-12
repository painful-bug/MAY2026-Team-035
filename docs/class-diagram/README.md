# HomeBandhu — UML Class Diagrams (PlantUML)

Two coordinated class diagrams. Kept separate so each renders legibly at
submission scale; together they cover the whole system.

| File | Scope |
|---|---|
| [`homebandhu-domain.puml`](homebandhu-domain.puml) | **Domain model** — 47 domain classes + 5 membership subclasses, abstract bases, interfaces, value objects, ~38 enums, association classes, all associations with multiplicities, and every constraint note. This is the primary deliverable. |
| [`homebandhu-architecture.puml`](homebandhu-architecture.puml) | **Application architecture** — FastAPI controllers/guards/DTOs → services → `Repository<T>` + concrete repositories → infrastructure gateways and external Supabase systems. |

## Renders are current — 2026-08-10

`HomeBandhu-Domain-Model.svg` / `.png` were regenerated on 2026-08-10 from the
`.puml` as it stands after migrations `0034`–`0046` (Service Personnel package,
departure scheduling dates, `DEPARTURE_REMOVAL`, and the Direct Messages classes).
Rendered with PlantUML **1.2024.8** + Graphviz **15.1.1** (`dot`). The previous
renders are preserved in [`../archives/2026-08-10-diagram-rerender/`](../archives/2026-08-10-diagram-rerender/)
with a note on what changed. Two render pitfalls that bit and are now known:

- **PNG size limit**: PlantUML clips PNGs at 4096×4096 by default — the previously
  committed PNG was silently truncated to that. Render with
  `-DPLANTUML_LIMIT_SIZE=24576`; the full diagram is ~21500 px wide.
- **Java version**: PlantUML **1.2025.0 and later require Java 11**. On a Java 8
  machine use `plantuml-1.2024.8.jar` (the last Java-8-compatible release).

## Pre-rendered output (ready to submit)

These are already generated — just open them:

- `HomeBandhu-Domain-Model.svg` / `.png`
- `HomeBandhu-Architecture-Layers.svg` / `.png`

Use the **SVG** for the report — it is vector and stays crisp scaled to A1.

## ⚠️ Do NOT use the free online renderers for these

They are too large for the hosted/free renderers:

- **plantuml.com website** encodes the whole diagram into the page URL → the URL
  exceeds the server limit → **400 Bad Request**.
- **kroki.io (free tier)** has a per-render complexity cap → **400 Internal Server
  Error** on any large diagram.

Neither is a problem with the `.puml` — they render perfectly offline.

## How to re-render (after editing a `.puml`)

You need `plantuml.jar` + Graphviz `dot` (the layout engine). Java 8+ is enough.

```bash
# 1. Get PlantUML (once):
#    https://github.com/plantuml/plantuml/releases  -> plantuml-<ver>.jar
# 2. Get Graphviz (once) and note the path to dot.exe:
#    Windows portable zip: GitLab graphviz releases -> windows_10_cmake_Release_Graphviz-*-win64.zip
#    or:  winget install Graphviz.Graphviz   (needs admin)
# 3. Render:
export GRAPHVIZ_DOT="/path/to/Graphviz/bin/dot.exe"   # Windows: set the env var to dot.exe
java -jar plantuml.jar -charset UTF-8 -tsvg homebandhu-domain.puml homebandhu-architecture.puml
java -jar plantuml.jar -charset UTF-8 -tpng homebandhu-domain.puml homebandhu-architecture.puml
```

**VS Code alternative:** install the *PlantUML* extension (jebbs) + Graphviz, open
the `.puml`, `Alt+D` to preview, right-click → *Export Current Diagram* → SVG.

> Note: PlantUML's no-Graphviz engine (`!pragma layout smetana`) renders the
> architecture file but **crashes on the domain file** (its ranking code throws on
> the dense relationship graph). Use real Graphviz `dot` — that is how the committed
> SVG/PNG were produced.

## Rendering into Eraser

Eraser's **AI diagram generator** produces ER-style output only (no methods,
inheritance, or layers), so it is not suitable for a true class diagram. Use the
PlantUML output instead. If the diagram must live in Eraser, paste the exported
SVG/PNG as an image.

## Model notes (must match the ERD)

- Role lives on `CommunityMembership` (5-subclass hierarchy), **never** on `Profile`.
  There is no `users(id, role)` class.
- `MembershipRole` is a fixed enum: RESIDENT, WORKER, SECURITY, MANAGER, ADMIN.
  *Technician* / *serviceman* are `Skill`s of a WORKER, not roles.
- `auth.users` and Supabase Storage are external systems (dashed / white boxes).
- Every `TenantScopedEntity` carries `communityId`; Postgres RLS isolates tenants.

> Source of truth is `docs/plan.md` (target schema). The current
> `backend/supabase/migrations/0001_init.sql` is mid-migration (still has
> `profiles.role` and a `TECHNICIAN` enum value) and does **not** yet match these
> diagrams — note this in the submission if asked.
