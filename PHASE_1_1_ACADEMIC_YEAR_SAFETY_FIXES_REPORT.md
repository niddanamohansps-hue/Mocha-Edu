# Phase 1.1 — Academic Year Safety Fixes Report

## 1. Problem
Three immediate correctness problems identified in the Phase 1.0 analysis:
1. **Frontend calendar-year defaults.** Seven pages and the admission wizard defaulted academic-year selectors to `String(new Date().getFullYear())`, producing `"2026"`. Tenant data may use `"2026-27"`, so reads returned empty results with no error, and writes could store the wrong value.
2. **Attendance calendar-year fallback.** `AttendanceSessionBulkSerializer._resolve_academic_year` returned `str(date.year)` when a section had no roster year. A session dated 2026-09-15 could store `"2026"` even when the section's enrollments use `"2026-27"`.
3. **Unknown years accepted in bulk enrollment.** `course_content` `bulk_enroll` accepted any non-empty string and wrote rows without a transaction, so a typo created enrollments for a year that exists nowhere else.

## 2. Frontend Fix
**Affected files** (all under `tenant_frontend/src/`):
- `app/dashboard/examinations/page.tsx` — exam year selector
- `app/dashboard/examinations/grading/page.tsx` — grade-boundary year selector
- `app/dashboard/fees/collect/page.tsx` — fee year
- `app/dashboard/fees/reports/page.tsx` — outstanding-report year (URL state)
- `app/dashboard/fees/structures/page.tsx` — fee-structure year
- `app/dashboard/timetable/page.tsx` — period year
- `app/dashboard/students/promotion/page.tsx` — source and target year
- `components/dashboard/students/AdmissionWizard.tsx` — enrollment default

**Old behavior:** each page initialized its year with `String(new Date().getFullYear())`, and the admission wizard's default was `new Date().getFullYear().toString()`.

**New behavior:** no calendar year is generated anywhere in `src/`. The affected screens start with an empty year:
- **Read-only views** (examinations, grading, fee reports, fee structures, timetable): an empty value sends no `academic_year` filter, so the API returns the unfiltered set. The existing hooks already treat an empty value as "no filter".
- **Promotion:** the source and target year default to empty. Preview is disabled while either is empty, so no promotion request can be built from an invented year.
- **Admission wizard:** the year defaults to empty. The schema already requires `academic_year` (`min(1)`), so the form cannot submit a blank value.
- Removed the now-unused `currentYear()` and `nextYear()` helpers. No `getFullYear` call remains in `src/`.

**How the year is obtained:** the user types or selects it. No existing endpoint lists the tenant's years, so the screens do not offer a selector sourced from data. This is the least invasive correct behavior the phase allowed; a populated selector needs the future `AcademicYear` API.

**Limitation:** the year fields are still free-text inputs. A user who types `2026` on a `YYYY-YY` tenant still gets empty results. This phase removes the silent invented default, not the free-text input.

## 3. Attendance Fix
**Old fallback:** `_resolve_academic_year(section, date)` took the year from the section's roster if one existed, otherwise `str(date.year)`.

**Authoritative source used:** the section's current enrollment. `StudentLevel` rows with `section_id=section.id, is_current=True`, reading `academic_year`. This is the same relationship the roster already uses, so no new relationship was introduced.

**New behavior:**
- The year always comes from the section's current enrollment. It is never derived from the attendance date.
- A section with no current enrollment is refused with a validation error on `section`, rather than guessed. Attendance saving already requires every submitted student to be on the roster, so this only changes behavior for a section that has no enrollments at all.
- The method signature changed from `(section, date)` to `(section)` because the date is no longer used. The only caller was updated.

## 4. Bulk Enrollment Fix
**Validation source:** the distinct `StudentLevel.academic_year` values already stored for the current tenant. This is the existing authoritative set. No `AcademicYear` table was created.

**Unknown-year behavior:** a year not present in that set returns **HTTP 400** with `{"error": "Unknown academic year '<value>'. Use a year that exists for this school."}`. Nothing is written.

**Transaction behavior:** the enrollment loop is wrapped in `transaction.atomic()`. Validation happens before the transaction opens, so an invalid year writes nothing. A failure partway through the loop rolls back all rows from that request.

**Preserved behavior:** a valid known year returns the same response shape and counts as before.

**Docstring:** the example payload year changed from `"2081"` to `"2026-27"`, so the documentation no longer shows a value the endpoint now rejects.

## 5. Data Normalization
**No existing academic-year values were automatically normalized.** No data was converted, backfilled, or rewritten. `"2026"` and `"2026-27"` remain as stored. Mapping them requires the human decision described in Phase 1.0.

## 6. AcademicYear Model
**No AcademicYear model was introduced.** No migration, foreign key, constraint, or schema change was made.

## 7. Tests

**Backend — new tests**
- `attendance/tests.py` — `AcademicYearFallbackTests` (3 tests):
  - a session dated in calendar year 2026 keeps school year `2026-27` (Test A)
  - the resolved year equals the current enrollment's year, not the date (Test B)
  - a section with no current enrollment is refused rather than guessed (Test C)
- `course_content/tests.py` — `BulkEnrollAcademicYearTests` (5 tests):
  - a known year (`2026-27`) enrolls every student
  - an unknown year (`2099-00`) returns 400
  - an unknown year writes no rows
  - a year existing only in another tenant is not valid here, and nothing is written to the other tenant
  - a user without `manage_subject_enrollment` gets 403

**Test results**
- Focused attendance and bulk-enrollment tests: **8 run, 8 passed**. The first bulk-enrollment run had a missing `User` import in the test file; it was fixed and the suite passed on rerun (5/5).
- Regression run `manage.py test payments academics staff profiles organizations attendance students examinations fees course_content timetable --keepdb`: **412 tests run, all passed**, in 5,552.8 seconds (about 92 minutes).

This includes the Phase 0.1 payment security tests, the Phase 0.2 payment amount tests, and the Phase 0.4 academics, staff, profiles, and organizations tests.

**Frontend**
- The regression run above covers backend only.
- `tenant_frontend` has no frontend test framework, so no frontend test was added. The phase instructions prohibit introducing one.

## 8. Frontend Validation

| Check | Result |
|---|---|
| `tsc --noEmit` (project-wide) | **PASS**, 0 errors |
| `eslint` on the 8 changed files | **15 errors, 3 warnings, all pre-existing** |

The ESLint findings are `@typescript-eslint/no-explicit-any` errors and unused-import warnings in lines this phase did not touch. Checking the diff for `any` found no new occurrences from this phase. The baseline was not separately measured, so this confirms only that no new `any` was introduced.

**Build:** `next build` was not run. The type check passing covers the changed code paths.

## 9. Database
**No schema changes.** No migrations.

## 10. Files Changed

Backend:
- `backend/attendance/serializers.py` — attendance fallback
- `backend/attendance/tests.py` — `AcademicYearFallbackTests` appended
- `backend/course_content/views.py` — bulk-enroll validation and transaction; example year corrected
- `backend/course_content/tests.py` — `BulkEnrollAcademicYearTests` appended, plus `User` import

Frontend:
- `tenant_frontend/src/app/dashboard/examinations/page.tsx`
- `tenant_frontend/src/app/dashboard/examinations/grading/page.tsx`
- `tenant_frontend/src/app/dashboard/fees/collect/page.tsx`
- `tenant_frontend/src/app/dashboard/fees/reports/page.tsx`
- `tenant_frontend/src/app/dashboard/fees/structures/page.tsx`
- `tenant_frontend/src/app/dashboard/timetable/page.tsx`
- `tenant_frontend/src/app/dashboard/students/promotion/page.tsx`
- `tenant_frontend/src/components/dashboard/students/AdmissionWizard.tsx`

Created: this report.

Earlier phases' changes (0.1–0.4, 1.0) were already present in the working tree and were not modified in this phase.

## 11. Follow-up Findings (deliberately deferred)

These need the future `AcademicYear` model or the migration plan:
- **Free-text year inputs remain.** Users can still type `2026` on a `YYYY-YY` tenant. A populated selector needs an `AcademicYear` API.
- **The `"2026"` vs `"2026-27"` split in stored data** is untouched. It needs the human mapping from Phase 1.0.
- **Bulk-enroll validation is against values already present.** It accepts any year that exists in `StudentLevel` even if that year is wrong, because no authoritative year list exists yet.
- **Other uses of `date.year` and string years on the backend** (for example, `populate_test_data.py` and the seeders) are not runtime academic-year logic and were not changed.
- **Promotion `targetYear` is now typed by hand.** The previous "next year" helper was removed; the future model should derive the target year from the source.
- **Pre-existing lint debt** in the touched files (`no-explicit-any`, unused imports) was not addressed; it is unrelated to these fixes.

## 12. Git
- **No commit.** No push.
- **No staging.**
- **Existing working-tree changes preserved.** No destructive git commands were run.
- New untracked file from this phase: `PHASE_1_1_ACADEMIC_YEAR_SAFETY_FIXES_REPORT.md`.
