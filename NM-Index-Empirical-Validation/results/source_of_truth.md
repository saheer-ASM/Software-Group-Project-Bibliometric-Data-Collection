# Source of truth for the isolated validation system

| Scope | Current authoritative file | SHA-256 |
|---|---|---|
| NM mathematical model, component definitions, Equations 1–27 and manuscript comparisons | [`Nm Index novel model (1)(3).pdf`](../source_documents/Nm%20Index%20novel%20model%20%281%29%283%29.pdf), 39 pages | `3bffd57d10b334bf4e37d437bf6babe6a9ae333cada1e6102be9181539ebdb91` |
| Empirical research questions, experiment procedures, stated statistical tests and required output tables | [`Pasted markdown(7).md`](../source_documents/Pasted%20markdown%287%29.md) | `0ec5857ff77d449ac9fb6ea131ebb7ce9755ce411af14e309dce478316896b8a` |

Both complete files were read in this phase. Their hashes are checked again by `src/pipeline.py` for every dry/mock/database run. Older NM PDFs are not used. The manuscript's Section 1.3 RQ1–RQ5 are *model-development* questions; the design's RQ1–RQ11 are the authoritative **empirical** experiment identifiers. Source conflicts and absent operational choices stay explicit in [the methodology reference](nm_methodology_reference.md), [baseline audit](baseline_implementation_audit.md), and [RQ audit](rq_implementation_audit.csv). A missing definition is not filled by an uncited formula.
