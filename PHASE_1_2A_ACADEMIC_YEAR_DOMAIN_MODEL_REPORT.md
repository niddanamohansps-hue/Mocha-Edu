# Phase 1.2A — AcademicYear Domain Model Report

## 1. Baseline git status
Recorded before any change: 32 entries (pre-existing work from Phases 0.1–1.1 and the analysis reports, all preserved).

## 2. Architecture inspected
- Tenant model: schema-per-tenant via django-tenants. `academics` is in `TENANT_APPS`, so its tables exist once per school.
- Existing year concepts: none. `StudentLevel.is_current` is per-enrollment, not per-year. No `AcademicYear` or `Year` model existed.
- Constraint conventions: `UniqueConstraint` is not used anywhere else in the repo. `unique_together` is the house style. Partial unique constraints are new to this codebase.
- Validation convention: `GradeBoundary.clean()` enforces ranges in Python and is called from `save()`. This phase follows that pattern.
- Primary keys and timestamps: UUID pk, `auto_now_add`/`auto_now` timestamps, matching all `academics` models.
- RBAC: existing `view_academic_level`-style codenames. No new permission was added (out of scope).
- Migrations: `academics` had `0001_initial` only, with no pending changes before this phase.

## 3. Chosen model location and rationale
`academics.AcademicYear`. The `academics` app already owns the school structure (Program, AcademicLevel, Section, Subject) and is tenant-local. An academic year is part of that structure, so this is its natural home. No new app was created. This matches the Phase 1.0 recommendation of a tenant-local entity.

## 4. Final AcademicYear model design
```
AcademicYear
  id           UUID pk, default uuid4
  name         CharField(20)           unique within tenant (DB constraint)
  start_date   DateField
  end_date     DateField
  is_current   BooleanField(default=False)   at most one True per tenant (DB constraint)
  created_at   auto_now_add
  updated_at   auto_now
  Meta.ordering = ["-start_date"]
```

## 5. Validation rules
Enforced in `clean()` (called by `full_clean()`):
- **Name format:** must match `YYYY-YY` with consecutive years (`2026-27` valid; `2026`, `2026-2027`, `2026-28`, `26-27`, `abc`, empty, and trailing whitespace are rejected). Invalid names are rejected, never repaired.
- **Dates:** `start_date < end_date`. Equal dates and end-before-start are rejected on `end_date`.

Not added (no evidence in the architecture for them): overlap prevention between years, minimum or maximum duration, and calendar-specific rules.

## 6. Tenant isolation approach
Tenant isolation is provided by the schema itself. Each school's `academics_academicyear` table is separate, so the same name in two tenants is valid, and the uniqueness constraint is naturally scoped to one tenant. The model has no `tenant` foreign key, which matches every other tenant-local model.

## 7. Uniqueness constraints
- `academicyear_name_unique`: `UNIQUE (name)` in each tenant schema. Global uniqueness is not enforced, because each schema has its own table.

## 8. Current-year constraint
- `academicyear_one_current`: partial unique index `UNIQUE (is_current) WHERE is_current`. Verified in the database (see §13). This is a real PostgreSQL constraint, not an application check.
- Non-current years are unlimited (tested).
- No automatic deactivation: creating a new current year does not clear another. This is an explicit choice, as the phase requires. A second current year fails with `IntegrityError`.

## 9. Migration details
- File: `academics/migrations/0002_academicyear.py`.
- Operations: a single `CreateModel(AcademicYear)` with its two constraints. No `AlterField`, `RemoveField`, `RunPython`, or changes to any other app.
- Applied with `manage.py migrate_schemas --noinput` across all tenant schemas in the dev database.

## 10. Tests added
`academics/tests.py`, class `AcademicYearModelTests` — 13 tests:
- Creation: valid year; multiple years coexist.
- Tenant isolation: same name valid in another tenant.
- Uniqueness: duplicate name in same tenant rejected by the database.
- Dates: start before end valid; equal dates rejected; end before start rejected.
- Name format: bare year, inconsistent years, wrong format, empty, and trailing whitespace rejected; name not silently normalized.
- Current year: one current allowed; second current in same tenant rejected by the database; current years in different tenants allowed; non-current years unlimited.
- Existing data safety: `students_studentlevel`, `attendance_attendancesession`, `examinations_examination`, `fees_studentfee`, `timetable_timetableentry` still have their `academic_year` varchar column and no `academic_year_id` FK column.

## 11. Test results
- `manage.py test academics.tests.AcademicYearModelTests --keepdb`: **13 run, 13 passed** (after two fixes: test helper argument count, and switching pure validation tests from `full_clean()` to `clean()`, since `full_clean()` runs a database check against the public schema).
- Regression: `manage.py test payments academics course_content attendance core organizations --keepdb`: **146 run, 146 passed**, 864.3 s.
  - Includes the Phase 0.1 and 0.2 payment tests (`payments`), the Phase 0.4 `academics`/`organizations` tests, and the Phase 1.1 attendance and bulk-enrollment tests (`attendance`, `course_content`).
- Not run: the full project suite. `students`, `examinations`, `fees`, `staff`, `profiles`, and `timetable` were not included in this run. The migration only adds a new empty table, so these apps' behavior is unchanged, but this is not a full regression.

## 12. `manage.py check` result
`System check identified no issues (0 silenced).` — **PASS**.

## 13. Database verification
Checked in the dev database's four tenant schemas (`greenvalley_demo`, `spsghy`, `sunrisevalley_school`, `test_chk`):
- `academics_academicyear` table present in all four.
- `academicyear_name_unique` — `CREATE UNIQUE INDEX ... (name)` present in all four.
- `academicyear_one_current` — `CREATE UNIQUE INDEX ... (is_current) WHERE is_current` present in all four.
- Existing academic-year values, snapshotted before and after the migration from `students_studentlevel`, `fees_studentfee`, and `attendance_attendancesession`: **identical**.
  - `greenvalley_demo`: `['2025','2026']`, `['2026']`, `['2026']`
  - `sunrisevalley_school`: `['2025-26','2026-27']`, `['2026-27']`, `['2026-27']`
  - `spsghy`, `test_chk`: empty.

No existing academic-year table or column was altered. No rows were created in the dev tenants by this migration; the new table is empty.

## 14. Files changed
- `backend/academics/models.py` — `AcademicYear` model appended.
- `backend/academics/migrations/0002_academicyear.py` — new, generated migration.
- `backend/academics/tests.py` — `AcademicYearModelTests` class, plus imports (`DjangoValidationError`, `IntegrityError`, `transaction`) and a `CHAR_VARYING_OID` constant.

Created: this report.

## 15. Files intentionally not changed
- No student, attendance, examination, fee, course-content, timetable, or parent-portal model or field.
- No serializer, view, service, URL, or permission.
- No frontend file. No AcademicYear UI.
- Neither seeder (`seed_demo_school.py`, `seed_realistic_school.py`).
- No existing migration. No data.

## 16. Pre-existing working-tree changes preserved
All entries from the baseline are unchanged. No file was staged, committed, or pushed, and no destructive git command was run.

## 17. Limitations and follow-up risks
- **No API yet.** The model has no serializer, viewset, or endpoints. Nothing can create an academic year through the application until the Phase 1.2B API exists; the dev tenants have no rows.
- **No activation workflow.** `is_current` can be set directly, but there is no service that switches it atomically. Switching requires clearing the old flag first in the same transaction, or a `DataError`/`IntegrityError` occurs. This must be handled in the future API.
- **Name format is `YYYY-YY` only.** The Phase 1.0 analysis found `"2081"`-style Bikram Sambat values in the codebase; those cannot be represented. Accepting other calendars is a product decision and was not made here.
- **No overlap check.** Two years with overlapping dates are allowed. This was not added because the architecture has no evidence for a rule. It should be decided before the API.
- **Existing free-text fields remain.** Until the later mapping phase, the `"2026"` vs `"2026-27"` split in stored data is not resolved.
- **`full_clean()` checks the database.** The model's uniqueness rules are checked by the database, so `full_clean()` on a non-tenant connection fails. Callers must run validation inside the tenant context.
- **Partial-index portability.** The `is_current` constraint is a PostgreSQL partial index. It is correct for this project's PostgreSQL-only setup.
