# Phase 1.3B — Decisions Recorded (Implementation Still NOT Approved)

**Status: decisions recorded only. No code, migration, model, serializer, view, service, frontend, seeder, or test file was changed. No database data was changed. Nothing was staged, committed, or pushed.**

This supplies explicit answers to the 7 open items in `PHASE_1_3A_ACADEMIC_YEAR_FK_MIGRATION_DESIGN_REPORT.md` §11. The decision block ends with `PHASE_1_3B_IMPLEMENTATION_APPROVED = NO`, so it authorizes planning against these answers, not a start of implementation.

## Decisions

| # | Item | Decision | Governs |
|---|---|---|---|
| 1 | StudentFee vs FeeStructure year consistency | `REQUIRE_MATCH_WITH_FEE_STRUCTURE` — Step C's validation report (§8/§9 of 1.3A) must enumerate every existing mismatch before any enforcement; existing mismatched historical records must not be silently rewritten. | Step C report design; Step D's eventual write-path validation; Step F's constraint scope. |
| 2 | GradeBoundary missing-year behavior | `PRESERVE_DURING_MIGRATION` — the current silent-ungraded behavior (§3.3 of 1.3A) is not changed by the FK migration itself. A separate, explicitly approved task must define stricter validation for new writes and grading operations. Existing boundaries are never discarded or reassigned by the migration. | Step D scope boundary; creates a follow-up task, not part of 1.3B. |
| 3 | SubjectEnrollment / AttendanceSession validation gaps (generic serializer writable but unvalidated, §3.1/§3.2 of 1.3A) | `TRACK_SEPARATELY` — out of scope for the FK migration. A separate, separately-approved validation-hardening task will close these. The FK implementation must not weaken what validation already exists. | Excludes items 3 of 1.3A §11 from 1.3B's diff. |
| 4 | Seeder changes (`seed_demo_school.py`, `seed_realistic_school.py`, `populate_test_data.py`) | `UPDATE_ONLY_WHEN_REQUIRED_FOR_DUAL_WRITE` — `seed_demo_school.py` stays untouched unless a dual-write requirement makes a change unavoidable, and any such change must preserve existing behavior and data. Year-format normalization (the `"2026"` vs `"2024-25"` inconsistency found in 1.3A §3.3) is explicitly NOT bundled into the FK backfill — a separate concern if it is ever addressed at all. | Step B/D seeder touch-points; keeps seed_demo_school.py's standing protection intact. |
| 5 | Frontend scope | `SEPARATE_PHASE` — Phase 1.3B stays backend-only. No frontend file changes. The eventual report/implementation must document the API compatibility contract (response/request shape for the FK-backed fields) the frontend phase will need, but must not implement against it. | Excludes all of 1.3A §3.7 and §10's frontend file list from 1.3B's diff. |
| 6 | Sunrise `2024-25` GradeBoundary exception | `KEEP_NULL_FK_AS_DOCUMENTED_EXCEPTION` — the six existing rows are unchanged; `academic_year_ref` may be NULL for these rows only, with explicit validation recognizing them as the documented exception (not an unexplained null). Step F's constraint-tightening must exclude these six rows or revisit the exception before tightening — not silently tighten over them. No Sunrise `2024-25` AcademicYear row is created without new, separate approval. | Step A nullability design (confirms §4/§6 of 1.3A is adopted as-is); Step F scope. |
| 7 | Incidental frontend bugs (`fees/collect` empty academic_year; `attendance/reports` missing year-filter forwarding) | `TRACK_IN_SEPARATE_FIX_PHASE` — not fixed as part of 1.3B, even incidentally. Tracked for a dedicated fix phase. | Explicitly excludes these from any future 1.3B diff, even if touched files overlap. |

## Effect on the Phase 1.3A Plan

These decisions narrow Phase 1.3B's eventual scope relative to the open questions in 1.3A §11, but do not change the staged plan itself (§5 and §8 of 1.3A: nullable FK → backfill → validate → dual-write → observe → tighten constraints → legacy removal in a later phase). Specifically:
- Item 1 adds a concrete requirement to Step C's validation report (enumerate StudentFee/FeeStructure mismatches) and to Step D (enforce going forward) without specifying how pre-existing mismatches are resolved — that remains a decision for whoever reviews Step C's actual output, not something to resolve speculatively now.
- Items 2 and 3 remove two items from 1.3B's diff entirely, each becoming its own future, separately-approved task.
- Item 4 keeps seeder changes minimal and reversible-in-spirit — only what dual-write strictly requires.
- Item 5 confirms Phase 1.3B produces no frontend diff; it does add a documentation deliverable (the API contract) that Phase 1.3B's eventual report must include once implementation is approved.
- Item 6 confirms the nullable-FK design in 1.3A §4/§6 is adopted exactly as proposed, with Step F required to handle the exception explicitly rather than by omission.
- Item 7 keeps both known frontend bugs out of scope, including as an incidental side-effect of other work.

## Next Step

`PHASE_1_3B_IMPLEMENTATION_APPROVED` remains `NO`. No migration, model change, or code change should begin until that value is explicitly flipped to `YES` (or equivalent explicit go-ahead) in a future message. This document only records the policy answers to plan against when that approval is given.
