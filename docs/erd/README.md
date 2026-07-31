# `docs/erd/` — which file is which

Two DBML files live here and they are **not** interchangeable.

| File | What it is | Status |
|---|---|---|
| `homebandhu-v1-milestone1.dbml` | The **milestone-1 submission ERD**, 48 tables. Verified byte-identical to the team's supplied `er-dbml.txt` on 2026-07-29. | **Authoritative.** Owned and maintained by the teammates handling the ERD. |
| `homebandhu.dbml` | A 63-table **v2 draft** produced during backend planning. Resolves many known defects in v1 (see `../MILESTONE1_ARTIFACT_ISSUES.md`) but was never agreed as the team artifact. | **Working draft only.** Do not treat as authoritative. |

Known issues in the authoritative v1 file are catalogued in
[`../MILESTONE1_ARTIFACT_ISSUES.md`](../MILESTONE1_ARTIFACT_ISSUES.md) — issues are recorded there
rather than fixed here, because the ERD is maintained elsewhere.

The rendered ER diagram image is generated from the `.dbml` on dbdiagram.io. Whenever the
authoritative file changes, the image needs regenerating from it — the `.dbml` is the source of
truth, the image is a projection.
