# Phase 1.2D Academic Year Decision Worksheet

**Mode:** read-only evidence review. No database writes, migrations, seeder changes, or frontend changes were made.
**Sources:** live queries against `edusekai_db` (read-only session), `PHASE_1_2C_ACADEMIC_YEAR_DATA_MAPPING_AUDIT_REPORT.md`, `PHASE_1_2D_BLOCKED_DECISIONS_REPORT.md`, and a repository search for calendar definitions.

**Authoritative calendar source found in the repository: NONE.** Every date below is either data evidence (not authoritative) or a seeder/test assumption (not authoritative). See the calendar section.

---

## Green Valley

### Legacy 2025
Recommended mapping: **NO SAFE MAPPING.** Options considered: `2025 = 2024-25` or `2025 = 2025-26`. The choice depends on decision for `2026`, so they must be decided together.
Confidence: **LOW**.
Evidence:
- Supports `2025` as the *prior* session: all 437 `2025` enrollments have `is_current = false`, and all 437 promotion records run `2025 → 2026`.
- Students carry the same admission-date span (2016 to 2026-06-28) under both `2025` and `2026`, so admission dates do not separate the two sessions.
- Grade bands exist for `2025` (7 rows), with no dates.
- Promotion `created_at` values are all 2026-10-02 (the seed run time), so they are not school evidence.
Human decision required: **YES**. Decide `2025 = 2024-25` or `2025 = 2025-26`, together with the `2026` decision.

### Legacy 2026
Recommended mapping: **NO SAFE MAPPING.** Two candidate readings, each supported by different evidence:
- Reading A: `2026 = 2025-26` (session Aug 2025 to Mar 2026).
- Reading B: `2026 = 2026-27` (session Apr 2026 onward).

Confidence: **LOW** for either reading.

Evidence for Reading A (2025-26):
- Exams: all 5 exams run 2025-08-10 to 2026-03-10.
- Attendance: 1,080 sessions, 2026-01-28 to 2026-03-31 (Jan 72, Feb 480, Mar 528); no attendance after March.
- Fees: 368 fees due Jan 2026 (fits mid-session).
- Grade bands and timetable (9 periods, 369 entries) carry no dates.

Evidence for Reading B (2026-27):
- Fees: 1,532 fees are due **April 2026**, the natural start of a session that begins in April.
- Current flag: 475 `2026` enrollments have `is_current = true`, so the school's live state already treats `2026` as current. The 2026 session has already run its exams and attendance, so either the school has moved on or the current flag is stale.
- Seeder: `seed_demo_school` sets `BASE_YEAR = 2026` as "the current academic year".

Evidence against both: attendance, exams, and the 2026 enrollments all stop in March or June 2026, while today is October 2026, so no data covers the current period.

Human decision required: **YES**. Choose Reading A or B and record the reason.

---

## Sunrise Valley

Sunrise Valley's labels are `YYYY-YY` and are internally consistent (verified in Phase 1.2C). Per-year presence, from live data:

| Year | Students | Attendance | Exams | Fees | Other | Evidence strength |
|---|---|---|---|---|---|---|
| 2024-25 | **0** | **0** | **0** | **0** | 6 grade-band rows only | None beyond grade bands |
| 2025-26 | 558 enrollments (not current) | 0 | 0 | 0 | 558 promotion sources, 6 grade bands | History |
| 2026-27 | 600 enrollments (all current) | 3,960 sessions | 4 exams, 1,020 schedules, 1,752 results | 2,841 fees | 558 promotion targets, 6 grade bands | Live |

### 2024-25
Create AcademicYear row: **DO NOT CREATE (recommended).**
Confidence: **HIGH** that no student-facing data exists for this year.
Evidence: no enrollments, attendance, exams, fees, timetable, or course content. The only references are 6 grade-band rows, which are configuration, not a session. Creating a row would add an empty session to every selector.
Human decision required: **YES**, only if the school wants this session listed for historical grade bands. Otherwise leave it out.

### 2025-26
Create AcademicYear row: **CREATE** (existence is well supported).
Confidence: **HIGH** that the session exists (558 students were enrolled and promoted from it). Dates: **LOW** confidence (see calendar).
Evidence: 558 enrollments, 558 promotion source records, 6 grade bands.
Human decision required: **YES** for the start and end dates only.

### 2026-27
Create AcademicYear row: **CREATE**.
Confidence: **HIGH** that the session exists and is live. Dates: **LOW** confidence.
Evidence: all live data (600 current enrollments, 3,960 attendance sessions, all exams and fees, 558 promotion targets).
Human decision required: **YES** for the start and end dates.

---

## Calendar Dates

**Authoritative evidence in the repository: none.** No settings value, fixture, configuration file, API payload, or documentation defines any session boundary. The seeder and tests are not authoritative.

Classification:
- **Data span (inferred, not authoritative):** attendance and exam date ranges above.
- **Seeder convention (assumption, not authoritative):** `seed_realistic_school.py` uses April 1 as the session start (its docstring: "the school's effective academic-year-start reference point"). This is a seed choice, not school policy.
- **Test fixtures (assumption, not authoritative):** the Phase 1.2A/1.2B tests use 2026-04-01 to 2027-03-31. These are arbitrary fixture values and must not be used as school dates.

### Green Valley
- 2024-25: Start: **HUMAN DECISION REQUIRED** — End: **HUMAN DECISION REQUIRED**
- 2025-26: Start: **HUMAN DECISION REQUIRED** — End: **HUMAN DECISION REQUIRED**
- (Green Valley's two session dates depend on the §Legacy 2025/2026 decision. Do not fill them until that is decided.)

### Sunrise Valley
- 2024-25: Start: **HUMAN DECISION REQUIRED** — End: **HUMAN DECISION REQUIRED** (row not recommended; see above)
- 2025-26: Start: **HUMAN DECISION REQUIRED** — End: **HUMAN DECISION REQUIRED**
- 2026-27: Start: **HUMAN DECISION REQUIRED** — End: **HUMAN DECISION REQUIRED**

Note: the April 1 convention is plausible for Indian private schools, but this repository does not establish it. Confirm the real session start and end dates from the school.

---

## Current Academic Year

**Sunrise Valley**
- Candidate: **2026-27**.
- Evidence: all 600 current enrollments are `2026-27`; the only live attendance, exam, and fee data is `2026-27`; the newest session covers Jun to Oct 2026, which contains today's date (2026-10-06).
- Confidence: **HIGH** on the data. The seeder's `is_current` flag is a seed choice, not a school decision.
- Human confirmation required: **YES**. Confirm the school considers `2026-27` the current session.

**Green Valley**
- Candidate: **NONE SAFE TO SET.** The live `is_current` flag sits on the `2026` label, but what `2026` means is undecided.
- Evidence: 475 current enrollments and 1,532 April 2026 fees point to `2026-27`; the attendance and exams end March 2026 and point to `2025-26`. Today (2026-10-06) is after both.
- Confidence: **LOW**.
- Human confirmation required: **YES**, after the §Legacy 2026 decision. The newest label is not automatically current.

---

## Final Human Decisions Required

1. **Green Valley `2026` meaning:** `2025-26` (Reading A) or `2026-27` (Reading B). Explain why.
2. **Green Valley `2025` meaning:** `2024-25` or `2025-26`. Must be consistent with decision 1.
3. **Sunrise `2024-25`:** confirm do-not-create (recommended), or give a reason to keep it.
4. **Sunrise session dates** (`2025-26`, `2026-27`): official start and end of each.
5. **Green Valley session dates** for the two sessions from decisions 1 and 2: official start and end of each.
6. **Sunrise current year:** confirm `2026-27` (or name another).
7. **Green Valley current year:** name the current session, or state that none should be set until the mapping is decided.
8. **Production status:** confirm whether `greenvalley_demo` and `sunrisevalley_school` are demo-only, and whether `spsghy` (empty) and `test_chk` (empty) should be excluded.

---

## Decision Checklist

```text
GREENVALLEY_2025_MAPPING =
GREENVALLEY_2026_MAPPING =

SUNRISE_2024_25_START_DATE =
SUNRISE_2024_25_END_DATE =

SUNRISE_2025_26_START_DATE =
SUNRISE_2025_26_END_DATE =

SUNRISE_2026_27_START_DATE =
SUNRISE_2026_27_END_DATE =

GREENVALLEY_FIRST_YEAR_START_DATE =
GREENVALLEY_FIRST_YEAR_END_DATE =

GREENVALLEY_SECOND_YEAR_START_DATE =
GREENVALLEY_SECOND_YEAR_END_DATE =

SUNRISE_CURRENT_YEAR =
GREENVALLEY_CURRENT_YEAR =

CREATE_SUNRISE_2024_25_ROW =
```
