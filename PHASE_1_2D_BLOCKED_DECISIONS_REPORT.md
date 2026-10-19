# PHASE 1.2D — BLOCKED: Required Decisions Missing

**Status: BLOCKED.** No data was written. No AcademicYear row was created. No legacy value was changed. No migration was generated.

The decision block supplied with this phase lists **every required decision as `UNDECIDED`**. The phase instructions require stopping before any data write when any decision is undecided. Guessing any of these values would silently shift dates, reports, and current-year behaviour for real or demo school data.

## Baseline (read-only checks run for this report)
- `git status --short`: **40 entries** (prior phases' work, unchanged by this report).
- AcademicYear rows: **0** in `greenvalley_demo`, `sunrisevalley_school`, `spsghy`, `test_chk`.

No write was issued. The checks were read-only `SELECT` statements on a read-only session.

---

## 1. Missing decisions

| # | Decision | Current value |
|---|---|---|
| 1 | `GREENVALLEY_2025_MAPPING` | UNDECIDED |
| 2 | `GREENVALLEY_2026_MAPPING` | UNDECIDED |
| 3 | `SUNRISE_2024_25_START_DATE` / `END_DATE` | UNDECIDED |
| 4 | `SUNRISE_2025_26_START_DATE` / `END_DATE` | UNDECIDED |
| 5 | `SUNRISE_2026_27_START_DATE` / `END_DATE` | UNDECIDED |
| 6 | `GREENVALLEY_FIRST_YEAR_START_DATE` / `END_DATE` | UNDECIDED |
| 7 | `GREENVALLEY_SECOND_YEAR_START_DATE` / `END_DATE` | UNDECIDED |
| 8 | `SUNRISE_CURRENT_YEAR` | UNDECIDED |
| 9 | `GREENVALLEY_CURRENT_YEAR` | UNDECIDED |
| 10 | `CREATE_SUNRISE_2024_25_ROW` | UNDECIDED |

---

## 2. Decision detail

### Decision 1 & 2 — Green Valley legacy mappings (`2025`, `2026`)
- **Why required:** the legacy labels are single-year, while the new model is `YYYY-YY`. Each label must map to exactly one named session.
- **Affected tenant:** `greenvalley_demo`.
- **Affected legacy values:** `2025` (437 student-level rows, 7 grade-band rows, 437 promotion source rows) and `2026` (500 student-level rows, 1,900 fee rows, 1,080 attendance sessions, 1,900 exam results, 5 exams, 480 schedules, 9 periods, 369 timetable entries, 7 grade-band rows, 437 promotion target rows).
- **Evidence conflicts (from Phase 1.2C):** exams, attendance, and fees for `2026` fall between August 2025 and April 2026, which suggests `2025-26`. Enrollment admission dates for both years extend to June 2026, which suggests otherwise.
- **Consequence of guessing:** if `2026` is wrongly mapped to `2026-27`, every exam, fee, and attendance date in that school would appear in the wrong year. Reports and the promotion history (`2025 → 2026`) would be misaligned by one year. The error would be silent.
- **Exact decision required:** state, in writing, which session each label means. For example: `2025 = 2024-25 and 2026 = 2025-26`, or `2025 = 2025-26 and 2026 = 2026-27`.

### Decision 3, 4, 5 — Sunrise Valley session dates (`2024-25`, `2025-26`, `2026-27`)
- **Why required:** every AcademicYear row needs a `start_date` and `end_date`. No calendar is stored anywhere in the database; the dates can only be inferred from data spans, which the phase forbids.
- **Affected tenant:** `sunrisevalley_school`.
- **Affected legacy values:** `2024-25` (6 grade-band rows only), `2025-26` (558 student-level rows, 558 promotion source rows, 6 grade-band rows), `2026-27` (600 student-level rows, 3,960 attendance sessions, 2,841 fees, 1,752 exam results, 4 exams, 1,020 schedules, 558 promotion target rows, 6 grade-band rows).
- **Evidence (not authoritative):** `2026-27` data falls between June and October 2026. This suggests an April to March session, but the boundaries are unconfirmed.
- **Consequence of guessing:** an incorrect end date would make the model's date-range validation accept or reject the wrong values, and would mislabel any future date-based filter.
- **Exact decision required:** the official start and end date of each session, for example `2026-27: 2026-04-01 to 2027-03-31`.

### Decision 6 & 7 — Green Valley session dates
- **Why required:** the same reason as decisions 3 to 5. The phase cannot create AcademicYear rows for Green Valley without them.
- **Affected tenant:** `greenvalley_demo`.
- **Consequence of guessing:** the exam and fee date evidence (Aug 2025 to Apr 2026) would be contradicted by any boundary the audit assumed.
- **Exact decision required:** the official start and end dates of the two sessions chosen in decision 1 and 2.

### Decision 8 — Sunrise Valley current year
- **Why required:** the model allows at most one current year per tenant, and the phase forbids assuming the newest year. The audit's evidence suggests `2026-27`, but it is not confirmed.
- **Affected tenant:** `sunrisevalley_school`.
- **Consequence of guessing:** the current year controls default selections and reporting. A wrong current year would make default views show the wrong session.
- **Exact decision required:** the exact year to mark current (one of `2024-25`, `2025-26`, `2026-27`, or none).

### Decision 9 — Green Valley current year
- **Why required:** the newest Green Valley data (attendance and exams) ends around March 2026, while today is October 2026. The audit cannot determine whether the school has moved on.
- **Affected tenant:** `greenvalley_demo`.
- **Consequence of guessing:** the same as decision 8, plus the risk that the chosen year has no data in the current period.
- **Exact decision required:** which Green Valley session is current, or that no current year should be set yet.

### Decision 10 — Create `2024-25` for Sunrise Valley
- **Why required:** `2024-25` appears only in grade bands (6 rows), with no enrollments, attendance, or fees. Creating a row adds an academic session the school may not recognise.
- **Affected tenant:** `sunrisevalley_school`.
- **Consequence of guessing:** an unwanted session would appear in every year selector, and deleting it later requires it to be non-current and free of dependents.
- **Exact decision required:** yes or no.

---

## 3. Items that cannot be resolved by this phase
- **Whether either tenant is production.** `greenvalley_demo` and `sunrisevalley_school` are seeded demo data. `spsghy` and `test_chk` are present but empty. The phase requires this to be confirmed, not assumed.
- **Whether `spsghy` should be included.** It is empty, so no mapping is needed, but no decision was supplied about it.

---

## 4. Phase 1.3 readiness
**NO.** The following blockers prevent the dual-column FK migration:
1. Green Valley legacy mappings (decisions 1 and 2) are undecided.
2. Session dates for all sunrise and Green Valley sessions are undecided (decisions 3 to 7).
3. Current year for both tenants is undecided (decisions 8 and 9).
4. Creation of `2024-25` for Sunrise is undecided (decision 10).
5. No AcademicYear rows exist in any tenant.

---

## 5. Data safety
- Legacy fields changed: **NO**
- Business data changed: **NO**
- AcademicYear rows created: **NO**
- Destructive operations: **NO**
- FK migration performed: **NO**
- Migrations generated: **NO**

## 6. Files
- **Created:** this report only.
- **Modified:** none.

## 7. Next step
Return the completed decision block with every value filled in explicitly. Acceptable values are concrete dates (YYYY-MM-DD), explicit mappings, and yes/no. Vague values such as "probably", "latest", or "auto" will be rejected. Phase 1.2D will then run against those values.
