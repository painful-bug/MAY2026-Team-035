# Archived diagram render — replaced 2026-08-12

One file, and the same rule as the [2026-08-10 archive](../2026-08-10-diagram-rerender/)
beside it: an image that silently disagrees with its source is worse than no
image, so the image is replaced and the old one kept here for provenance.
Nothing in this folder is a source of truth.

## What is in this folder

| File | Was rendered from | Why it was replaced |
|---|---|---|
| `erd.svg` | `docs/diagrams/homebandhu_submission_erd.dbml` | Rendered 2026-08-11, before the deployment boundary. Missing the four tables the `20260811`–`20260812` migrations add — `service_signup_funnel_events`, `department_skills`, `staff_invitations` and `complaint_department_requests` — and the notes on the two views those files replace. |

## How the replacement was made

Same toolchain and same command as 2026-08-10, run offline:

```bash
cd docs/diagrams
npx @softwaretechnik/dbml-renderer -i homebandhu_submission_erd.dbml -o erd.svg
```

The pipeline is deterministic and was verified before the source was touched:
re-rendering the **unmodified** `.dbml` reproduced the committed `erd.svg`
byte-for-byte (md5 `375fb26c8dc680ec02a6cf6df4a45572`). So the only difference
between the archived file and the new one is the four tables.

## Two renders that could NOT be refreshed, and are therefore stale

Stated plainly rather than left to be discovered, because both files are still
sitting in `docs/diagrams/` and `docs/class-diagram/` looking current:

| Stale file | Needs | Not available here |
|---|---|---|
| `docs/diagrams/erd.png` | Graphviz `dot`, fed the renderer's `-f dot` output | no `dot` on this machine, and none bundled with the npm package |
| `docs/diagrams/HomeBandhu-Architecture-Classes.png` | `plantuml.jar` | no jar present; Java 8 is installed, so `plantuml-1.2024.8.jar` is the version to fetch (`1.2025.0+` needs Java 11) |
| `docs/class-diagram/HomeBandhu-Domain-Model.svg` / `.png` | `plantuml.jar` **and** Graphviz `dot` | same missing jar, plus the domain file cannot use `smetana` — its ranking code throws on that relationship graph, which is why the 2026-08-10 renders were made with real `dot` |

`docs/class-diagram/README.md` still says **"Renders are current — 2026-08-10"**. That
sentence expired when `homebandhu-domain.puml` gained `DepartmentSkill`,
`StaffInvitation`, `ServiceSignupFunnelEvent` and `StaffInvitationStatus` on
2026-08-12, and correcting it was outside the fence of the pass that wrote this
note. It needs one line struck.

Neither was archived, because neither was replaced — they are still the only
PNGs the repository has. The `.puml` **source** for the second one was updated
in the same pass and is correct; only its PNG is behind. That file carries
`!pragma layout smetana`, so it renders **without Graphviz** once a jar is
present:

```bash
java -jar plantuml-1.2024.8.jar -charset UTF-8 -tsvg -tpng \
  -DPLANTUML_LIMIT_SIZE=24576 docs/diagrams/HomeBandhu-Architecture-Classes.puml
```

The size flag is not optional — PlantUML clips PNGs at 4096×4096 by default,
which is how the previous domain-model PNG lost its right-hand 80 % without
anyone noticing (see the 2026-08-10 note).

## Why this happened at all

The five-gate rule says every schema change checks the ERD and the class
diagram, and `docs/` holds **three** ERD files and **three** class-diagram
files. Seven migrations landed between 2026-08-11 and 2026-08-12; the gate was
passed for `docs/erd/homebandhu.dbml` and `docs/class-diagram/homebandhu-domain.puml`
— and even there only for `complaint_department_requests`, not for its two
sibling tables — and was not passed at all for either artifact in
`docs/diagrams/`. A gate applied to one copy of an artifact is not a gate.
