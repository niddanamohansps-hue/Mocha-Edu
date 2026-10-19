# PHASE 1.0 — Academic Year Architecture Analysis

**Type:** Read-only analysis. No application code, models, migrations, tests, seeders, frontend, or database were changed.

## 1. Executive Summary

EduSekai has no `AcademicYear` entity. An academic year is a free-text `CharField(max_length=20)` copied into 13 model fields across six apps. It carries no start date, end date, active flag, or uniqueness. Nothing enforces that two sources spell the same year the same way.

The dev database already shows two incompatible formats in live tenants:

- `greenvalley_demo`: `"2025"`, `"2026"`
- `sunrisevalley_school`: `"2025-26"`, `"2026-27"`

These are different strings for the same school year, so a filter on one format silently returns nothing for data written in the other. The frontend defaults most year selectors to `String(new Date().getFullYear())`, which produces the single-year form and would show empty results against the `YYYY-YY` data.

**Recommendation:** introduce a tenant-local `AcademicYear` model with explicit dates and a single current-year rule, and migrate the 13 string fields to foreign keys in staged, reversible steps. The migration cannot be fully automatic, because `"2026"` and `"2026-27"` cannot be mapped to a single canonical year without a human decision. This is the main risk and is covered in section 11.

## 2. Current Academic-Year Architecture

- **Storage:** `CharField(max_length=20)` in each model. No `AcademicYear` model exists anywhere in `backend/`.
- **Validation:** the only validator is `students/services.py:validate_academic_year`, which rejects blank, whitespace-only, and values longer than 20 characters. It applies no format policy. Its own docstring states this is deliberate.
- **Derivation:** `attendance/serializers.py:_resolve_academic_year` falls back to `str(date.year)` when a section has no roster year. This writes a year format that differs from any roster-derived value.
- **Client-supplied:** every year is supplied by the client (request body or query string). Nothing derives a year from a date on the server, except the attendance fallback above.
- **Hard-coded:** `course_content/views.py` bulk-enroll docstring example uses `"2081"`, a Bikram Sambat (Nepali) year. This is an unvalidated example, not a server default.
- **Seeders:** `seed_demo_school.py` uses `str(BASE_YEAR - n)`, producing `"2025"`/`"2026"`. `seed_realistic_school.py` uses `"YYYY-YY"`, producing `"2025-26"`/`"2026-27"`. Both write directly and bypass any validation.

## 3. Complete Dependency Map

Year-scoped models (13 field definitions):

| App | Model | Field | Notes |
|---|---|---|---|
| students | StudentLevel | academic_year | `unique_together=(student, academic_year)`; one row per student per year |
| students | PromotionRecord | source_academic_year, target_academic_year | `blank=True`, not required |
| attendance | AttendanceSession | academic_year | unique per (section, date) |
| examinations | Examination | academic_year | |
| examinations | ExamSchedule | academic_year | |
| examinations | ExamResult | academic_year | immutable publish snapshot |
| examinations | GradeBoundary | academic_year | `ordering=["academic_year", ...]`, overlap check scoped by year |
| fees | FeeStructure | academic_year | |
| fees | StudentFee | academic_year | indexed `(student, academic_year)` |
| course_content | SubjectEnrollment | academic_year | `unique_together=(student, subject, academic_year)` |
| timetable | TimetablePeriod (Period) | academic_year | `unique_together=(academic_year, order)` |
| timetable | TimetableEntry | academic_year | unique across section/instructor/room per day+period; indexed |

Indirect dependency (no year field, but year-scoped through a related row): `StudentFee` snapshots `level_name`/`section_name` at assignment because `StudentLevel` keeps no per-year section history beyond its own row.

Consumers by area:

- **Students:** enrollment (`StudentLevel`), promotion candidates and execute (`students/services.py`), promotion history.
- **Academics:** no year field of its own. `Program`, `AcademicLevel`, `Section`, `Subject`, `SubjectAssignment` carry none. Teacher assignment is year-independent today, so one assignment serves every year. This is a real gap for historical accuracy.
- **Attendance:** session creation, roster year fallback, `history` and report filters.
- **Examinations:** exam creation, schedule validation, grading boundaries, results, parent results.
- **Fees:** structures, student fees, outstanding report, payment history.
- **Parent/family:** portal results and fees filter by year (`parent_portal/views.py`).
- **Timetable:** entry validation and conflict checks (`timetable/services.py`) scope by year.
- **Course content:** bulk-enroll, subject enrollment.
- **Admissions:** not implemented. The admission wizard collects `academic_year` as free text (`AcademicInfoStep.tsx`).
- **Reporting/dashboard:** dashboard and reports filter by year string.
- **Notifications:** no year field. Not year-scoped.
- **Seeders:** both create year strings directly (section 14).

Models with no year (do not change): Program, AcademicLevel, Section, Subject, SubjectAssignment, StaffMember, Instructor, Parent, StudentParentRelation, Room, TimetableSubstitution, CourseContent, Assignment, AssignmentSubmission, Student, AcademicHistory, FeeHead, Payment, PaymentAllocation, ExamType, ExamMark, StudentAttendance, StaffAttendance, AttendanceSettings, Notification, EmailOutboxEvent.

## 4. Current Data Model

Per-field facts (all 13 are `CharField(max_length=20)`):

- **Nullable:** no. **Required:** yes, except `PromotionRecord.source/target_academic_year` (`blank=True`, default `""`).
- **Default:** none.
- **Indexed:** only through composite indexes: `StudentFee (student, academic_year)`, `TimetableEntry` (`academic_year, day_of_week`).
- **Unique:** only through composites (`StudentLevel`, `SubjectEnrollment`, `TimetablePeriod (academic_year, order)`, `TimetableEntry` slot tuples).
- **Populated by:** client input on create, seeders, or the attendance fallback.

## 5. Current Business Semantics

Answered from the code, not from intent:

- **Is `2026-27` only a label?** Yes. It is compared for string equality. No code parses it.
- **Start/end dates?** None exist.
- **Overlapping years?** Possible. Nothing prevents two strings from covering the same period (`"2026"` and `"2026-27"`).
- **Current/active year?** Not modelled. `StudentLevel.is_current` is per-enrollment, not per-year. The frontend hard-codes "current" as the calendar year.
- **Only one current year per tenant?** Not enforced.
- **Future years?** Possible. Nothing blocks writing a year in advance.
- **Historical edits?** Possible. A `StudentLevel` or `StudentFee` can be created against any year string at any time.
- **Year change:** the promotion engine writes a new `StudentLevel` for the target year and a `PromotionRecord` with both year strings. Reversal creates a compensating record.
- **Enrollment/exams/fees by year:** yes, via the string field on each row.
- **Derived from dates?** Only the attendance fallback, and only from a date's calendar year.
- **Client-supplied?** Yes, always, except that attendance can fall back to the calendar year.

## 6. Data Integrity Risks

Concrete examples from the code and live data:

1. **Inconsistent spelling/format across tenants.** `greenvalley_demo` uses `"2026"`; `sunrisevalley_school` uses `"2026-27"`. Both are valid under the validator.
2. **Mixed formats within one tenant.** Attendance fallback writes `"2026"` into a session whose roster uses `"2026-27"`. Filtering attendance by year then splits the same school year into two buckets.
3. **Cross-year leakage through the frontend default.** Selectors default to `new Date().getFullYear()`. For a `YYYY-YY` tenant this is `"2026"`, which matches no rows. Users see empty reports with no error.
4. **Non-existent years accepted.** `"9999"`, `"abc"`, or `"2081"` pass validation. `course_content/views.py` bulk-enroll requires only a truthy value.
5. **Unenforced uniqueness.** Nothing prevents creating `"2026"` and `"2026-27"` as two independent years. Duplicate-year checks cannot be written at the database level.
6. **No date boundaries.** Exam dates, fee due dates, and timetable entries are not checked against any year range.
7. **Orphaned references.** There is no parent row to delete or rename. A typo in one table's year leaves that data unreachable from the others.
8. **Ambiguous current year.** `StudentLevel.is_current` is per student, while the frontend uses the calendar year. A student promoted to a new year and a fee assigned to the old year can both appear "current" depending on the screen.
9. **Difficult historical reporting.** Comparing 2025 and 2026 across formats requires string normalization in every query.
10. **Promotion mismatch risk.** `get_promotion_candidates(academic_year, ...)` is driven entirely by the caller's string. A wrong string produces zero candidates with no error.
11. **Enrollment uniqueness depends on exact string.** `unique_together=(student, academic_year)` treats `"2026"` and `"2026-27"` as different years, so one student can hold two current-year rows.

## 7. Tenant Architecture Considerations

Recommendation: **tenant-local.**

- Each school has its own calendar, its own year boundaries, and its own choice of format. A global table would force one school's dates on another.
- The architecture already isolates per school by schema. A public `AcademicYear` table would need a tenant column and would leak year metadata across tenants, which conflicts with the schema-per-tenant design.
- Consequence: `AcademicYear` belongs in `TENANT_APPS` (one table per schema). Its foreign keys are local. Each school migrates on its own schedule.
- Cost: each tenant needs its own initial year rows. Provide a management step or first-login setup rather than a global seed.

## 8. Design Options

**Option A — keep strings.** Acceptable only as a short-term fallback. It cannot enforce uniqueness, date boundaries, or a single current year, and the format split in section 6 already causes wrong results. Not recommended long term.

**Option B — first-class `AcademicYear` model, FKs replace strings.** Enforces identity, dates, and current-year rules, and lets reports join on an integer-like key. Requires a careful data migration. Recommended.

**Option C — hybrid: add `AcademicYear`, keep the string fields alongside the FKs during transition.** Useful as a bridge. Lets reads switch gradually and gives a rollback path. Cost: two sources of truth during the window, so every write must set both. Recommended only as the migration mechanism inside Option B, not as a permanent design.

**Chosen path:** Option B delivered through Option C's transition window, then the strings are removed.

## 9. Recommended AcademicYear Model

Proposed (not implemented):

```
AcademicYear
  id              UUID pk (matches the project's UUID convention)
  name            CharField(20), unique within tenant, e.g. "2026-27"
  start_date      DateField
  end_date        DateField            (end_date > start_date, enforced in clean())
  is_current      BooleanField         (at most one True per tenant)
  created_at / updated_at
```

Constraints and rules:

- **Uniqueness:** `name` unique per tenant. Date-range overlap is rejected in application validation, matching how `GradeBoundary.clean()` enforces overlap today. A PostgreSQL exclusion constraint on `daterange(start_date, end_date)` would enforce it in the database; it needs the `btree_gist` extension, so decide whether that dependency is acceptable before choosing it.
- **Single current year:** a partial unique index `UNIQUE (is_current) WHERE is_current` guarantees at most one current year. Changing the current year is one atomic update that clears the old flag.
- **Multiple active years:** not allowed as "current", but past and future years are normal. "Active" means `is_current`; other years remain selectable for historical data.
- **Overlapping dates:** rejected (see above).
- **Deletion:** `PROTECT` from every year-scoped model. A year with any dependent row cannot be deleted; it can only be archived by a future flag, not in this phase.
- **Editing after dependent data exists:** `name` becomes read-only once any dependent row exists, because renaming silently breaks the string-era joins and reports. Dates may be corrected only with an audit entry, and only if the new range still contains all dependent rows' dates (for exams and sessions, check against their dates).
- **Audit:** every change to `is_current`, dates, or deletion writes an `AuditLog` entry through the existing `log_action()`.
- **Indexes:** `UNIQUE(name)` (tenant-local, implicit), partial unique on `is_current`. Date queries are small-table lookups; no extra index needed until profiling says so.

## 10. Model Relationship Migration Matrix

| Current Model | Current Field | Current Type | Proposed Relation | Migration Risk |
|---|---|---|---|---|
| students.StudentLevel | academic_year | CharField(20) | FK → AcademicYear, PROTECT | **High**: part of unique_together and promotion logic |
| students.PromotionRecord | source_academic_year | CharField(20), blank | FK source_year, nullable | Medium: history must keep original string as well |
| students.PromotionRecord | target_academic_year | CharField(20), blank | FK target_year, nullable | Medium: same |
| attendance.AttendanceSession | academic_year | CharField(20) | FK → AcademicYear | **High**: fallback writes calendar-year strings; unique (section, date) |
| examinations.Examination | academic_year | CharField(20) | FK → AcademicYear | Medium |
| examinations.ExamSchedule | academic_year | CharField(20) | FK → AcademicYear (should equal exam's year) | Medium: redundant with Examination; consider deriving |
| examinations.ExamResult | academic_year | CharField(20) | FK → AcademicYear | Medium: immutable snapshot, must not change historical meaning |
| examinations.GradeBoundary | academic_year | CharField(20) | FK → AcademicYear | Medium: overlap check and ordering use the string |
| fees.FeeStructure | academic_year | CharField(20) | FK → AcademicYear | Medium |
| fees.StudentFee | academic_year | CharField(20) | FK → AcademicYear | **High**: financial data, indexed with student |
| course_content.SubjectEnrollment | academic_year | CharField(20) | FK → AcademicYear | Medium: part of unique_together |
| timetable.TimetablePeriod (Period) | academic_year | CharField(20) | FK → AcademicYear | Medium: unique (academic_year, order) |
| timetable.TimetableEntry | academic_year | CharField(20) | FK → AcademicYear | **High**: conflict checks use year in several unique tuples |

Models that derive year indirectly and need attention: `StudentFee.level_name/section_name` snapshots (no year field, depends on StudentLevel), and `TimetableEntry` conflict logic which keys on year.

## 11. Production Migration Strategy

Staged, reversible, and gated on human review. The sequence below is adapted to this schema rather than copied from a template.

**Phase A — Create the table (additive).** Add `AcademicYear` in each tenant schema. No existing field changes. Safe to deploy alone.

**Phase B — Discover and map (read-only, per tenant).** Collect distinct values from all 13 fields. For each tenant, produce a mapping table `raw_value → AcademicYear`. Automatic mapping is only safe for values already in `YYYY-YY` form. Single-year values (`"2026"`) need a human decision: is `"2026"` the year starting 2026 (`2026-27`) or ending 2026 (`2025-26`)? Bikram Sambat values (`"2081"`) map to a different calendar and must be flagged. Malformed values are reported, not guessed.

**Phase C — Backfill new FK columns (additive).** Add nullable FK columns beside each string. Populate from the approved mapping. Do not drop anything.

**Phase D — Validate.** Check: no row with a non-null string and null FK; every FK points to a year whose name matches the string; `StudentLevel` uniqueness still holds per year; attendance fallback rows reviewed; NULL and blank strings handled explicitly (blank promotion fields map to NULL FK). Reconcile counts per table before and after.

**Phase E — Switch reads and writes.** Application reads use the FK; writes set both FK and string during the window (Option C). Filters accept either a year id or a name during transition, so existing clients keep working.

**Phase F — Remove strings.** Only after a full release cycle with no string reads and a clean validation report. Drop string columns and their unique/index constraints in a separate migration. This step is the only irreversible one.

**Handling specifics:**
- **Malformed strings:** stop the migration for that tenant and report the list; do not guess.
- **NULLs:** `StudentLevel.academic_year` and other required fields have no NULLs by constraint. `PromotionRecord` blank values map to NULL FK.
- **Duplicates:** two raw strings mapping to the same year (e.g. `"2026"` and `"2026-27"` both meaning one year) must be merged deliberately, which can collide with `unique_together` on `StudentLevel`, `SubjectEnrollment`, and `TimetableEntry`. Resolve duplicates before Phase D.
- **Backwards compatibility:** Phase C and E keep both columns, so a rollback to the string code path works until Phase F.
- **Deployment ordering:** A → B (manual review) → C → D → deploy code that reads FK with string fallback → E → (release cycle) → F.
- **Rollback:** before F, rollback is a code revert plus leaving extra nullable columns in place. After F, rollback requires restoring the string columns from the mapping table; treat F as a one-way gate.
- **Downtime:** Phases A–D are additive and can run online. E is a code deploy. Only F rewrites tables; schedule it, and index before dropping.

## 12. API Impact

Current input and proposed change for each affected endpoint:

| Area | Endpoint(s) | Current input | Proposed | Compatibility |
|---|---|---|---|---|
| Enrollment | `POST /api/students/enroll/` | `academic_year` string | `academic_year` as AcademicYear id, name still accepted during transition | Keep name input for old clients |
| Promotion | `GET /api/students/promotion/candidates/`, `POST .../preview/`, `.../execute/` | `academic_year` string, entry `target_academic_year` string | id or name | Name accepted during transition |
| Promotion history | `GET /api/students/promotion/history/` | returns year strings | returns both string and nested year | Additive |
| Attendance | sessions create/update, `reports/below-threshold/`, `students/{id}/history/` | `academic_year` in roster or query | id or name | Filters accept both |
| Examinations | exams, schedules, results, grading, `students/{id}/results/`, `reports/below-passing/` | `academic_year` string | id or name | Filters accept both |
| Fees | fee structures, assign, `students/{id}/`, outstanding report | `academic_year` string | id or name | Filters accept both |
| Parent portal | children results, fees, upcoming exams | `?academic_year=` | id or name | Filters accept both |
| Timetable | entries, periods | `academic_year` string | id or name | Unique tuples change meaning carefully |
| Course content | `POST .../bulk_enroll/` | `academic_year` string (example `"2081"`) | id | Must reject unknown years rather than accept any string |
| Dashboard | `GET /api/dashboard/summary/` | none (calendar-driven) | takes `academic_year` id; default = current year | Default prevents empty dashboard |
| Admissions | not implemented | n/a | future endpoints take year id | Build against AcademicYear from the start |

## 13. Frontend Impact

25 frontend files reference academic year. Grouped by behaviour:

- **Default to the calendar year** (`currentYear() = String(new Date().getFullYear())`): `dashboard/examinations/page.tsx`, `examinations/grading/page.tsx`, `fees/collect/page.tsx`, `fees/reports/page.tsx`. These produce the single-year format and mismatch `YYYY-YY` data. **Highest priority fix.**
- **Free-text entry:** `components/dashboard/students/AdmissionWizard.tsx`, `students/admission/AcademicInfoStep.tsx`. Replace with a select of AcademicYear rows.
- **Filter and query state:** hooks `useAttendance`, `useExaminations`, `useFees`, `usePromotion`, `useStudents`, `useTimetable`, `useDashboard`, and pages `fees/structures`, `students/promotion`, `timetable`, `dashboard`. Move year into URL query state, keyed by AcademicYear id, with the current year as default.
- **Types:** `types/Attendance.ts`, `CourseContent.ts`, `Examinations.ts`, `Fees.ts`, `ParentPortal.ts`, `Promotion.ts`, `Timetable.ts`. Change `academic_year: string` to an object with id and name.

Recommended consumption: one `useAcademicYears()` hook (array query key `["academic-years"]`), one shared year selector component, and a single `currentAcademicYear` value returned by the API rather than computed in each page.

## 14. Seeder Impact

Neither seeder should change in this phase. Both currently write year strings directly and will need updating after Phase E.

- **`seed_demo_school.py`:** `self.years = [str(BASE_YEAR - n)]`, producing `"2025"`/`"2026"`. After migration it must create AcademicYear rows first, then assign FKs. Its data also has the single-year format, so the mapping decision in Phase B applies directly.
- **`seed_realistic_school.py`:** creates `AcademicYear` strings `"2024-25"`, `"2025-26"`, `"2026-27"` and marks the last as current. After migration it must create the three AcademicYear rows with real dates (for example April to March), mark `"2026-27"` current, and keep its historical/current/future behaviour: promotion history creates `"2025-26"` records, and the current year is the newest row.
- The realistic seeder's dates are already implied by its format, so the mapping is straightforward for it. The demo seeder's are not.

## 15. Test Impact

**Existing tests that will change:** all tests that build year strings directly. That includes examinations, fees, attendance, students (promotion), timetable, parent_portal, course_content, and the realistic-seeder tests in `core/tests.py`. Expect several hundred literal occurrences; most change only fixture construction.

**New tests required:**
- creation: valid dates, `end_date > start_date`, name format rules;
- validation: overlap rejected, duplicate name rejected, invalid format rejected;
- current year: at most one current, atomic switch, cannot delete the current year;
- tenant isolation: a year in school A is invisible and unusable in school B;
- historical years: old year remains selectable and readable, not editable once dependents exist;
- dependent records: deleting a year with StudentLevel/StudentFee/etc. is blocked;
- API filtering: each endpoint accepts id and transitional name;
- migration correctness: mapping, backfill counts, duplicate and malformed-value handling, rollback path.

## 16. Performance / Indexing

- Expected queries: year-scoped filters on `StudentFee (student, year)`, `StudentLevel (student, year)`, `TimetableEntry (year, day)`, and report aggregates per year.
- `AcademicYear` is a tiny table (a handful of rows per tenant). Lookups by name, id, or `is_current` are trivially cheap; no index is needed beyond the implicit unique on name and the partial unique on `is_current`.
- The FK columns added in Phase C should be indexed before any query switches to them, because existing composite indexes on the string columns will not serve FK joins. Plan: add single-column indexes on each new FK, and rebuild composite indexes `(student, year_fk)` on StudentFee and StudentLevel.
- Dropping string columns (Phase F) removes their composite indexes, so the replacement indexes must exist first.
- Do not add these indexes in this phase.

## 17. Security / RBAC

- **Who may change the current year:** an admin-level permission (proposed codename, e.g. `manage_academic_year`), not ordinary staff. Changing the current year changes which records every default screen shows, so it is a configuration action.
- **Who may read years:** any authenticated user with a view permission on the area they are using. Years are not sensitive, but writes are.
- **IDOR:** a year id is tenant-scoped by schema, so cross-tenant access fails at the schema boundary. Within a tenant, object-level rules are needed for year edits only.
- **Unauthorized switching:** a non-admin must not be able to change `is_current` by posting to a generic endpoint. The check belongs in the service, not only the view.
- **Historical access:** unchanged. Past years remain readable under the same permissions as current data; the change does not widen access.
- **Audit:** all year writes are audited (section 9).

No permissions are implemented in this phase.

## 18. Risks and Rollback Strategy

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Ambiguous single-year values mapped to the wrong year | High | High (wrong dates on financial and exam data) | Human-reviewed mapping per tenant; no auto-guess |
| Duplicate years collide on `unique_together` | Medium | High | Resolve duplicates before Phase D |
| Client keeps sending old format after switch | Medium | Medium (empty results) | Accept name during transition; reject unknown with 400 |
| Attendance fallback keeps writing calendar-year strings | High if not fixed | Medium | Change fallback to resolve the current AcademicYear |
| Frontend default still calendar year | High today | Medium | Fix defaults first (section 13) |
| Dropping strings is irreversible | Certain | High | Gate Phase F behind a full release cycle and clean validation |
| Overlap check requires an extension | Medium | Low | Decide on btree_gist; app-level check otherwise |

**Rollback:** safe until Phase F (code revert; extra nullable columns are harmless). After F, restore strings from the mapping table, then revert code. Keep the mapping table as a permanent artifact.

## 19. Recommended Implementation Phases

1. **Fix the immediate harm (no schema change):** make the frontend stop defaulting to the calendar year; make attendance fallback use the roster year, not `date.year`; reject `"2081"`-style values at the bulk-enroll endpoint.
2. **Phase A–B:** add `AcademicYear`; generate the per-tenant mapping report; get it reviewed.
3. **Phase C–D:** backfill FKs and validate.
4. **Phase E:** switch services, serializers, filters, and frontend to ids (with name fallback).
5. **Phase F:** remove strings after validation, in its own release.

## 20. Explicit Out-of-Scope Items

- Implementing `AcademicYear` or any migration.
- Changing permissions or adding a `manage_academic_year` codename.
- Admissions module (not implemented; will depend on AcademicYear).
- Timetable redesign beyond year keys.
- Payroll, library, leave, and other modules from the gap analysis.
- Modifying either seeder or any test.
- Solving the float-based amount comparison in payment verification (separate backlog item).
- Bikram Sambat calendar support beyond flagging `"2081"`-style values.

---

**Git state:** verified before and after writing this report; only this file is new.
