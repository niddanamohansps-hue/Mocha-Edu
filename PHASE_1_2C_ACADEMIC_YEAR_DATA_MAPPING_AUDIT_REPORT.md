# Phase 1.2C — Academic Year Data Mapping Audit Report

**Type:** Read-only audit. No data, schema, migration, code, seeder, or frontend file was changed. The only file created is this report.

## 1. Baseline git status
Recorded before the audit: **39 entries** (prior phases' work, all preserved). After the audit, `git status --short` was compared line by line with the baseline and is **identical**.

## 2. Tenants inspected
Source: the `organizations_organization` table in the dev database `edusekai_db`.

| Schema | Type | Inspected | Academic-year rows |
|---|---|---|---|
| `greenvalley_demo` | demo (seed_demo_school) | yes | 937 student-level rows |
| `sunrisevalley_school` | demo (seed_realistic_school) | yes | 1,158 student-level rows |
| `spsghy` | real or manual tenant | yes | 0 (empty) |
| `test_chk` | test tenant | yes | 0 (empty) |
| `public` | shared schema | excluded | not a tenant |

Tenants were discovered from `organizations_organization` and filtered to non-public schemas, not a hard-coded list. The two empty tenants were inspected and reported, not skipped.

## 3. Academic-year fields discovered
Enumerated from `information_schema.columns` across all tenant schemas. **13 columns**, matching the Phase 1.0 model inventory. All are `character varying(20)`, `NOT NULL`, with no default.

| App | Table | Column | Used for |
|---|---|---|---|
| attendance | attendance_attendancesession | academic_year | session year |
| course_content | course_content_subjectenrollment | academic_year | subject enrollment |
| examinations | examinations_examination | academic_year | exam year |
| examinations | examinations_examresult | academic_year | published results |
| examinations | examinations_examschedule | academic_year | schedules |
| examinations | examinations_gradeboundary | academic_year | grade bands |
| fees | fees_feestructure | academic_year | fee structures |
| fees | fees_studentfee | academic_year | student fees |
| students | students_promotionrecord | source_academic_year | promotion source |
| students | students_promotionrecord | target_academic_year | promotion target |
| students | students_studentlevel | academic_year | enrollment year |
| timetable | timetable_period | academic_year | periods |
| timetable | timetable_timetableentry | academic_year | timetable entries |

Every field is `NOT NULL`, so nulls cannot exist. Filtering, writes, and API use were established in Phase 1.0 and are unchanged. The `academics_academicyear` table (Phase 1.2A) has no academic-year string column.

## 4. Distinct values per tenant (record counts)

### `greenvalley_demo`
| Table.column | Value | Rows |
|---|---|---|
| students_studentlevel.academic_year | `2025` | 437 |
| students_studentlevel.academic_year | `2026` | 500 |
| students_promotionrecord.source_academic_year | `2025` | 437 |
| students_promotionrecord.target_academic_year | `2026` | 437 |
| attendance_attendancesession | `2026` | 1,080 |
| fees_studentfee | `2026` | 1,900 |
| examinations_examination | `2026` | 5 |
| examinations_examschedule | `2026` | 480 |
| examinations_examresult | `2026` | 1,900 |
| examinations_gradeboundary | `2025` | 7 |
| examinations_gradeboundary | `2026` | 7 |
| timetable_period | `2026` | 9 |
| timetable_timetableentry | `2026` | 369 |

Distinct values in this tenant: **`2025`, `2026`**.

### `sunrisevalley_school`
| Table.column | Value | Rows |
|---|---|---|
| students_studentlevel.academic_year | `2025-26` | 558 |
| students_studentlevel.academic_year | `2026-27` | 600 |
| students_promotionrecord.source_academic_year | `2025-26` | 558 |
| students_promotionrecord.target_academic_year | `2026-27` | 558 |
| attendance_attendancesession | `2026-27` | 3,960 |
| fees_studentfee | `2026-27` | 2,841 |
| examinations_examination | `2026-27` | 4 |
| examinations_examschedule | `2026-27` | 1,020 |
| examinations_examresult | `2026-27` | 1,752 |
| examinations_gradeboundary | `2024-25` | 6 |
| examinations_gradeboundary | `2025-26` | 6 |
| examinations_gradeboundary | `2026-27` | 6 |

Distinct values in this tenant: **`2024-25`, `2025-26`, `2026-27`**.

### `spsghy`, `test_chk`
No rows in any of the 13 columns.

## 5. Cross-module consistency
- **`sunrisevalley_school`:** consistent. Every module uses `YYYY-YY` labels, and the current-year label `2026-27` is used by students, attendance, exams, fees, and schedules. The only other value, `2025-26`, appears as history (promotion source and prior enrollment) and in grade bands. No module uses a different format.
- **`greenvalley_demo`:** consistent in format. Every module uses the single-year form `2025`/`2026`. The current label `2026` appears in students, attendance, exams, fees, and timetable, and `2025` appears only as history.
- **Within-tenant format mixing:** **none found.** No tenant contains both `2026` and `2026-27`. The Phase 1.0 risk (attendance fallback writing `date.year`) is a latent risk, not a present one: no data currently carries a calendar-year value produced by that path.
- **Cross-tenant conflict:** yes. The two demo tenants use different conventions for what is nominally the same school year. A string-based filter cannot reconcile them, which is the core reason for the `AcademicYear` entity.

## 6. Temporal / date evidence

**`sunrisevalley_school`**
- `2026-27` attendance: 2026-06-01 to 2026-10-02 (3,960 sessions).
- `2026-27` exams: schedules 2026-07-01 to 2026-10-07.
- `2026-27` fees: due 2026-07-15.
- `2025-26` enrollments: admission dates from 2024-04-01.
- `2026-27` enrollments: admission dates from 2024-04-01 to 2026-06-28.

Evidence supports `2026-27` as a session running April 2026 to March 2027, with data consistent with that span. The `2025-26` history is consistent with the same convention.

**`greenvalley_demo`**
- `2026` attendance: 2026-01-28 to 2026-03-31 (1,080 sessions).
- `2026` exams: schedules 2025-08-10 to 2026-03-05 (exam header 2025-08-10 to 2026-03-02).
- `2026` fees: due 2026-01-15 to 2026-04-15.
- `2026` student enrollments: admission dates from 2016-06-02 to 2026-06-28.
- `2025` enrollments: admission dates to 2026-06-28, the same spread as `2026`.

Interpretation: attendance, exams, and fees for `2026` all fall between August 2025 and April 2026. That is consistent with an **academic session 2025-26 labelled `2026`** (named after the year it ends). The enrollment dates reach June 2026, which is not consistent with a session ending in March 2026, so this evidence conflicts. Each student's enrollment rows also carry the admission-date spread for both years, meaning the `2025` and `2026` enrollments are not separated by date.

**Conclusion:** the dates do not unambiguously determine what `2026` means. This is recorded as an unresolved ambiguity (§15).

## 7. AcademicYear table comparison
All four tenant schemas contain the `academics_academicyear` table (created in Phase 1.2A) with **0 rows** each.

| Tenant | Legacy values | AcademicYear rows | Status |
|---|---|---|---|
| greenvalley_demo | `2025`, `2026` | 0 | no rows exist |
| sunrisevalley_school | `2024-25`, `2025-26`, `2026-27` | 0 | no rows exist |
| spsghy | none | 0 | nothing to map |
| test_chk | none | 0 | nothing to map |

No potential match exists yet, because no AcademicYear row exists to match against. Every legacy value would require a new row.

## 8. Malformed / invalid values
A full scan of all 13 columns in all four tenants (regex `^\d{4}-\d{2}$` or `^\d{4}$`, plus null, blank, and whitespace checks) found **0 malformed rows**.

Not found in any tenant: `2026-2027`, `26-27`, `2026/27`, `2026_27`, `FY2026`, nulls, empty strings, whitespace padding, future-year anomalies, or the `2081` example from the course-content docstring.

Severity: **none in this dataset.** The `2081` value remains a documentation example only; it was not stored anywhere.

## 9. Proposed mappings

Legend: confidence is HIGH (the label itself is unambiguous and the dates agree), MEDIUM (likely, needs confirmation), LOW (multiple interpretations), or UNMAPPABLE.

| Tenant | Legacy value | Proposed AcademicYear | Confidence | Evidence | Action |
|---|---|---|---|---|---|
| sunrisevalley_school | `2026-27` | `2026-27` | HIGH (name) / MEDIUM (boundary dates) | Name is `YYYY-YY` consecutive; all data falls in Apr 2026–Mar 2027 | Human confirms school session start/end dates |
| sunrisevalley_school | `2025-26` | `2025-26` | HIGH (name) / MEDIUM (boundary dates) | History enrollments; admissions from 2024 | Same confirmation |
| sunrisevalley_school | `2024-25` | `2024-25` | HIGH (name) / MEDIUM (boundary dates) | Exists only in grade bands (no enrollments) | Confirm it is a real session worth keeping |
| greenvalley_demo | `2026` | `2025-26` **or** `2026-27` | LOW | Exams/attendance/fees fit 2025-26; enrollments extend to Jun 2026 | **Human decision required** |
| greenvalley_demo | `2025` | `2024-25` **or** `2025-26` | LOW | Follows whichever convention is chosen for `2026` | **Human decision required** (tied to the `2026` decision) |

**Important:** no automatic mapping is proposed for greenvalley. Choosing `2026 → 2025-26` would also make `2025 → 2024-25`, but that is a convention decision for the school, not something the data proves.

## 10. Confidence summary
- **HIGH:** the name identity of the `sunrisevalley_school` labels.
- **MEDIUM:** the exact boundary dates for the sunrise sessions (no school calendar is stored, only the data span).
- **LOW:** every greenvalley label, because the two interpretations are both supported by different parts of the evidence.
- **UNMAPPABLE:** none. Every value has at least one plausible interpretation; none is malformed.

## 11. Current-year candidates
Not set. Recorded for human confirmation only.

- **`sunrisevalley_school` → `2026-27`: likely current.** The audit was run on 2026-10-05. That date falls inside the span of `2026-27`, which is the newest label with live data. **Not confirmed**, because the school's calendar is not stored.
- **`greenvalley_demo`: no clear current year.** Its newest data (attendance and exams) ends around March 2026, while today is October 2026. The label `2026` is the newest in use, but the data is stale. **Not confirmed**, and the current-year decision depends on the §9 decision.

## 12. Proposed AcademicYear rows (REQUIRED / PROPOSED — NOT inserted)

**`sunrisevalley_school`** (name only; dates need a human-supplied school calendar):
- `2024-25`: referenced by grade bands
- `2025-26`: referenced by enrollments and promotion history, and by grade bands
- `2026-27`: referenced by all live modules; likely current

**`greenvalley_demo`** (pending the §9 decision; two alternative sets):
- If `2026 = 2025-26`: `2024-25` (for `2025`), `2025-26` (for `2026`)
- If `2026 = 2026-27`: `2025-26` (for `2025`), `2026-27` (for `2026`), with the attendance/exam dates considered anomalous for that session

**`spsghy`, `test_chk`:** none required.

Every AcademicYear row requires a `start_date` and `end_date`. These are **not present in the data**, so they must come from a human-supplied school calendar. None were invented here.

## 13. Tenant risk classification
- **`sunrisevalley_school`: REVIEW_REQUIRED.** All values are format-consistent and mostly unambiguous. The boundary dates are not stored, and the current year is not confirmed.
- **`greenvalley_demo`: HIGH_RISK.** Labels are single-year and genuinely ambiguous, the data conflicts (session dates versus enrollment dates), and the current year is stale relative to today. Mapping by default would silently shift every date-based report by a year.
- **`spsghy`: SAFE (no data).** Nothing to map. Safe to create AcademicYear rows at any time.
- **`test_chk`: SAFE (no data).** Test tenant; nothing to map.

## 14. Reasons for the risk levels
- **`sunrisevalley_school` REVIEW_REQUIRED:** the labels are unambiguous, but the dates needed to create complete AcademicYear rows (start/end) are not stored. Migration cannot complete without them.
- **`greenvalley_demo` HIGH_RISK:** two candidate mappings each fit part of the evidence; the enrollment dates contradict the session-end reading; and a wrong choice would shift every exam, fee, and attendance report for that school.
- **`spsghy`, `test_chk` SAFE:** no legacy data exists, so no mapping can damage anything.

## 15. Unresolved ambiguities
1. **Does `2026` in `greenvalley_demo` mean the session 2025-26 (ending 2026) or 2026-27 (starting 2026)?** Evidence supports 2025-26 for exams, attendance, and fees, but the enrollment dates extend to June 2026 and the seed's stated "current year" is 2026. This is the single most important unresolved question.
2. **What are the start and end dates for each session?** Not stored anywhere. Needed for all AcademicYear rows.
3. **Does `greenvalley_demo` have a current year, and which?** Its newest data is stale relative to today.
4. **Should the `2024-25` grade bands in `sunrisevalley_school` become an AcademicYear row, given there are no enrollments for it?**
5. **Is `spsghy` a real school whose data will arrive later?** It is empty, so the mapping for it is undefined until it has data.

## 16. Recommendations for human decisions
1. **Decide greenvalley's convention** (`2026` = 2025-26 or 2026-27) before any migration. Record the decision in writing, since it changes every report for that school.
2. **Supply session start and end dates** for each sunrise session and for greenvalley's chosen sessions. Without these, no AcademicYear row can be complete.
3. **Confirm sunrise's current year** (`2026-27`) and whether `2024-25` should exist as a row.
4. **Keep `spsghy` and `test_chk` out of the migration plan** unless they gain real data.
5. **Do not map the two demo tenants' conventions onto each other.** Their labels mean different things; each tenant's mapping is independent.
6. **Schedule the backfill only after the decisions above**, following the Phase 1.0 plan (add table, map, backfill FK alongside the string, validate, switch reads, drop strings in a separate release).

## 17. Confirmation that no data was modified
- Every database query was a `SELECT` executed on a session set to `readonly=True`. No `INSERT`, `UPDATE`, `DELETE`, or DDL statement was issued.
- `academics_academicyear` row count: 0 in all four tenants, unchanged.
- The 13 academic-year columns were not modified; the value distributions in §4 are the values at the time of the audit.
- `git status --short` after the audit is **identical** to the baseline (39 entries).
- `makemigrations --check`: **No changes detected**, so no migration is pending and none was generated.

## 18. Tests and results
No new code was written, so no new tests were added. No application behaviour changed, so the existing suites were not re-run; they remain as recorded in Phases 1.1, 1.2A, and 1.2B.

The audit queries are one-off reads run from a script that is not committed to the repository. They were not added as a management command, since the phase did not require one and the audit is a point-in-time analysis.

## 19. `manage.py check`
`System check identified no issues (0 silenced).` — **PASS**.

## 20. Files changed
- **Created:** `PHASE_1_2C_ACADEMIC_YEAR_DATA_MAPPING_AUDIT_REPORT.md` (this report).
- **Modified:** none in this phase.

## 21. Files intentionally unchanged
- No model, migration, serializer, view, service, URL, or permission.
- No frontend file.
- Neither seeder (`seed_demo_school.py`, `seed_realistic_school.py`).
- No existing data, including `"2026"`, `"2026-27"`, `"2025"`, `"2025-26"`, `"2024-25"`.
- No AcademicYear row (none created).

## 22. Limitations
- **Dev database only.** The audit covers `edusekai_db`. Production tenants were not inspected and may hold different values.
- **Point-in-time.** Values and counts reflect the dev data on the audit date. Demo tenants were seeded at known times, so their counts are fixed by the seeders, not by real usage.
- **Date evidence is inferential.** Dates show when records occurred, not what the school calls the session. Interpretation requires the school's own calendar.
- **No calendar data exists** anywhere in the database, so boundary dates are not verifiable from the audit.
- **Demo data reflects seeder assumptions.** The greenvalley seed uses `BASE_YEAR = 2026` for "current," which may encode the seeder author's convention rather than a school's real practice.
- **Did not check** attendance session dates against enrollment dates record by record; the summary min/max only.
- **Did not measure** the frontend's behaviour against each tenant's data (covered in Phase 1.1).
