# Phase 1.2D — Academic Year Decision and Backfill Report

## Executive Status: COMPLETE

This report supersedes the earlier `BLOCKED` version of this file. The authoritative decision block supplied for this execution had no `UNDECIDED` values. Four `AcademicYear` rows were created, exactly as decided: two in `sunrisevalley_school`, two in `greenvalley_demo`. No legacy field was changed. No migration was generated. No foreign key was added. `spsghy` and `test_chk` were not touched.

## Decision Block (as supplied, honoured verbatim)

| Tenant | Row | Start | End | Current |
|---|---|---|---|---|
| sunrisevalley_school | 2025-26 | 2025-04-01 | 2026-03-31 | No |
| sunrisevalley_school | 2026-27 | 2026-04-01 | 2027-03-31 | **Yes** |
| greenvalley_demo | 2024-25 | 2024-04-01 | 2025-03-31 | No |
| greenvalley_demo | 2025-26 | 2025-04-01 | 2026-03-31 | No |

| Tenant | Legacy value | Maps to |
|---|---|---|
| greenvalley_demo | `2025` | `2024-25` |
| greenvalley_demo | `2026` | `2025-26` |
| sunrisevalley_school | `2025-26` | `2025-26` |
| sunrisevalley_school | `2026-27` | `2026-27` |

- `sunrisevalley_school` legacy `2024-25` (6 grade-boundary rows only): **intentionally not created.** Those 6 rows are left as configuration with no corresponding `AcademicYear` row, per `CREATE_SUNRISE_2024_25_ROW = NO`.
- `greenvalley_demo` current year: **none set.** No Green Valley row is marked current.
- `spsghy`, `test_chk`: excluded, not processed, not touched.

## Implementation

- `backend/academics/backfill.py` — the decision block as code constants (`DECISIONS`), a pre-write validator (`validate_decisions`, no DB access — checks name format, consecutive years, start<end, at-most-one-current, mapping targets exist), an idempotent `apply_tenant` (tenant-scoped `transaction.atomic`, non-current rows inserted before the current row so the single-current DB constraint is never transiently violated, `full_clean()` before `save()`, one `AuditLog` entry per created row with action `academic_year_backfill_created`), and a read-only `validate_tenant` that checks every legacy value across the 13 legacy columns resolves to exactly one `AcademicYear` or the one approved exception.
- `backend/academics/management/commands/backfill_academic_years.py` — thin command wrapper; dry-run by default, `--apply` to write.

A conflicting pre-existing row with different values would raise and abort that tenant's write; re-running the command after a successful apply is a no-op (confirmed by the `apply_tenant` existing-row check).

## Execution Log

1. **Pre-write baseline** (prior to this execution): `git status --short` → 43 entries; legacy-column snapshot → `academicyear_rows=0` in both tenants; all 13 legacy columns' distinct values and counts recorded.
2. **Dry-run** (`backfill_academic_years`, no `--apply`): planned `create: 2025-26`, `create: 2026-27` for sunrisevalley_school; `create: 2024-25`, `create: 2025-26` for greenvalley_demo. No existing rows, no conflicts.
3. **Apply** (`backfill_academic_years --apply`): all four rows created as planned; sunrisevalley_school's `2026-27` is the only row marked current.
4. **Post-write verification** (direct tenant-scoped read): row values confirmed to exactly match the decision block (name, start_date, end_date, is_current) for both tenants.
5. **Legacy-field immutability check**: re-ran the identical read-only snapshot query used for the pre-write baseline. The only difference between before and after is `academicyear_rows` (0→2 in each tenant); all 13 legacy columns' distinct values and row counts are byte-for-byte identical.
6. **Mapping validation** (`validate_tenant`, read-only): for both tenants, `unmapped=[]`, `ambiguous=[]`, `orphan_rows=[]` — every legacy value in the 13 legacy columns resolves to exactly one `AcademicYear` row (or is the one approved, intentionally-unmapped exception), and every created `AcademicYear` row is referenced by the mapping.
7. **`manage.py check`**: `System check identified no issues (0 silenced)`.
8. **`manage.py makemigrations --check --dry-run`**: `No changes detected` — no model change, no migration drift.
9. **Tests**: `manage.py test academics attendance.tests.AcademicYearFallbackTests course_content.tests.BulkEnrollAcademicYearTests --keepdb` → `Ran 52 tests ... OK` (academics model/API/backfill-adjacent tests, plus the Phase 1.1 academic-year fallback and Phase 1.1 bulk-enroll validation suites).
10. **`git status --short` after vs. before**: identical 43 pre-existing entries, plus exactly two new untracked paths added by this phase (`backend/academics/backfill.py`, `backend/academics/management/`). No pre-existing change was altered or reverted. No destructive git command was run. Nothing was committed or pushed.

## Data Safety

- Legacy fields changed: **NO**
- Business data changed: **NO**
- AcademicYear rows created: **YES** — 4 (2 per tenant), exactly as decided
- Foreign keys added: **NO**
- Migrations generated: **NO**
- `spsghy` / `test_chk` touched: **NO**
- Destructive git operation run: **NO**
- Commit/push performed: **NO**

## Files

- **Created:** `backend/academics/backfill.py`, `backend/academics/management/__init__.py`, `backend/academics/management/commands/__init__.py`, `backend/academics/management/commands/backfill_academic_years.py`, this report (overwriting the prior `BLOCKED` version).
- **Modified:** none.
- **Data written:** 4 `AcademicYear` rows (tenant schemas `greenvalley_demo`, `sunrisevalley_school`), 4 corresponding `AuditLog` rows.

## Phase 1.3 Gate

**Is Phase 1.3 (dual-column FK migration) ready to start automatically? NO — not started, and not to be started without a separate, explicit approval.**

What this phase establishes that Phase 1.3 would build on:
- Every in-scope tenant now has `AcademicYear` rows covering every legacy value that is mapped, with validated, unambiguous mappings (confirmed in step 6 above).
- The one approved exception (`sunrisevalley_school` legacy `2024-25`) has no corresponding row by design; a future FK migration would need an explicit rule for rows carrying that legacy value (there are none — only grade-boundary configuration references it).
- `greenvalley_demo` has no current year; any future code path that assumes a current year exists for every tenant would need to handle that case.

This report does not authorize Phase 1.3. It remains a separate phase requiring its own explicit scope and approval.
