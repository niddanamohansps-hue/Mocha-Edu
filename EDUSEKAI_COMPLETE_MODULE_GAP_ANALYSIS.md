# EduSekai — Complete Module Gap Analysis & Implementation Roadmap

**Scope:** Analysis only. No code, database, migration, seeder, test, or git state was changed.
**Method:** Repository inspection of `backend/` (Django apps, URLs, views, serializers, services, models, admin, tests), `tenant_frontend/` (Next.js route tree), and `frontend/` (public site). Keyword sweeps were run for every missing-module term in the checklist.

**Evidence codes used in the matrix**

| Code | Meaning |
|---|---|
| Y | Present and confirmed in code |
| P | Partially present (model, endpoint, or screen exists, but workflow is incomplete) |
| N | Not found in code (keyword sweep and structure check) |
| ? | Not verified in this pass |
| — | Not applicable |

**Status legend**

| Icon | Status | Meaning |
|---|---|---|
| ✅ | IMPLEMENTED | Backend and required frontend exist and are usable |
| 🟡 | PARTIALLY IMPLEMENTED | Some components exist; workflow incomplete |
| 🔴 | MISSING | No meaningful implementation |
| 🟠 | NEEDS VERIFICATION | Possibly present; not confidently classified |
| 🔵 | FUTURE | Intentionally postponed |

---

## 1. Executive Summary

EduSekai is a multi-tenant school ERP with a solid **core**: tenant provisioning, authentication, RBAC, students, families, staff, academic structure, timetable, attendance, examinations with immutable publication, fees with safe payment allocation, course content and assignments, promotion with reversal, notifications, an outbox-based email pipeline, a parent portal, and a dashboard summary. Backend test coverage is strongest in the operational apps (fees, notifications, examinations, parent portal, attendance, students).

The product is **not yet a complete school ERP**. Whole modules are absent from both backend and frontend: **Admissions (applicant workflow), Library, Transport, Leave management, Inventory and Assets, Certificates and document management, Health, Activities, Campus/facility booking, and Payroll**. Several core modules exist only partially: **communication (announcements), fees (scholarships, installments, refund workflow, online fee payment), LMS (quizzes, progress), academic calendar, and reporting (no report hub, no transcript or rank)**.

Two architectural facts shape the roadmap:

1. **The online-payment integration is for school signup only.** `backend/payments/` implements an eSewa flow that creates a tenant after payment. It is **not** connected to student fee collection.
2. **Several "modules" exist as names without workflows.** `fees/signals.py` seeds fee heads named "Admission", "Transport", and "Library", but no transport or library module exists. This is misleading and should be documented or removed.

---

## 2. Current Architecture Summary

```
Next.js tenant_frontend  (dashboard, route tree below)
Next.js frontend         (public: get-started, payment-success)
        |  Axios, cookie JWT (withCredentials)
        v
Django + DRF   config/urls.py mounts one prefix per app under /api/
  TENANT_APPS (per-school schema): core, roles, profiles, students, staff, families,
    academics, course_content, attendance, timetable, examinations, parent_portal,
    fees, notifications, dashboard
  SHARED_APPS (public schema): accounts, organizations, payments
        |
        v
PostgreSQL  (schema-per-tenant via django-tenants)
        |
Redis  -> Celery broker only (notifications.tasks: send_outbox_email, recover_stale_outbox_events)
Celery Beat schedule defined in settings (every 10 min); orchestration not present in repo
```

**Tenant frontend route tree (confirmed):** academics, attendance (history, mark, reports, settings, staff), course-content (assignments, grading, manage, materials), examinations (grading, marks, results, root), fees (collect, my-fees, reports, structures), hr/recruit, faculty/onboarding, institution (roles, settings), instructors, notifications, parent-portal (attendance, children, fees, results, timetable, root), portal-access (staff, students), profile, staff (edit, onboarding, root), students (admissions, edit, promotion, root), timetable (my-schedule, root, substitutions), plus login, forgot-password, reset-password.

**Public frontend routes (confirmed):** `/`, `/get-started`, `/payment-success`.

**Backend test counts (confirmed by grep):** fees 95, students 85, examinations 73, timetable 44, attendance 40, core 43, notifications 64, parent_portal 52, dashboard 24, accounts 31, families 20, course_content 4, payments 3, roles 1. **Zero tests:** academics, staff, profiles, organizations.

---

## 3. Complete Feature Matrix (255 items)

Columns: **B** = backend, **F** = tenant frontend, **A** = API, **D** = database model, **T** = tests in owning app.
Priority: P0 Critical · P1 High · P2 Medium · P3 Low.

### A. Platform / SaaS Foundation

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Platform | Multi-tenant architecture | ✅ | Y | — | — | Y | Y | P0 | django-tenants, schema per school |
| 2 | Platform | Organization / school management | ✅ | Y | P | Y | Y | N | P1 | Register API and public signup; no tenant admin screen |
| 3 | Platform | Tenant domain / subdomain | ✅ | Y | — | Y | Y | N | P1 | check-domain endpoint; Domain model |
| 4 | Platform | Tenant isolation | ✅ | Y | — | — | Y | Y | P0 | Dedicated isolation tests in examinations, others |
| 5 | Platform | User management | 🟡 | P | N | N | Y | P | P1 | Users created via seeders and flows; no user admin UI |
| 6 | Platform | Authentication | ✅ | Y | Y | Y | Y | Y | P0 | Cookie JWT, login/logout/refresh/me |
| 7 | Platform | JWT / session management | ✅ | Y | Y | Y | Y | Y | P0 | 15 min access, 24 h refresh, blacklist on logout |
| 8 | Platform | Password reset | ✅ | Y | Y | Y | Y | Y | P0 | Token reset, email via outbox |
| 9 | Platform | Role-based access control | ✅ | Y | Y | Y | Y | P | P0 | HasPermission + owner wildcard |
| 10 | Platform | Permission management | ✅ | Y | Y | Y | Y | P | P1 | Roles UI, permission catalogue |
| 11 | Platform | Audit logging | 🟡 | Y | N | Y | Y | Y | P1 | Backend and API exist; no viewer screen |
| 12 | Platform | API security / throttling | 🟡 | P | — | P | — | P | P1 | Only 6 auth-adjacent scopes throttled |
| 13 | Platform | File / document storage | 🟡 | P | P | P | P | N | P1 | Local media only; production storage not verified (?) |
| 14 | Platform | Notifications | ✅ | Y | Y | Y | Y | Y | P0 | In-app inbox, unread count, mark read |
| 15 | Platform | Email / outbox system | ✅ | Y | — | — | Y | Y | P0 | Transactional outbox, retries, failure states |
| 16 | Platform | Background jobs / Celery | 🟡 | Y | — | — | — | P | P1 | Tasks implemented; worker/beat not orchestrated in repo |
| 17 | Platform | Redis infrastructure | 🟡 | P | — | — | — | — | P1 | Broker only; no cache |
| 18 | Platform | Reporting infrastructure | 🟡 | P | P | P | — | P | P1 | Per-module reports; no shared report engine or export |

### B. Student Management

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 19 | Students | Student registration | ✅ | Y | Y | Y | Y | Y | P0 | Enrollment wizard, admin side |
| 20 | Students | Student profile | ✅ | Y | Y | Y | Y | Y | P0 | Profile + detail page |
| 21 | Students | Student photo | 🟡 | P | ? | P | Y | N | P2 | profile_image field exists; upload UI not verified |
| 22 | Students | Student documents | 🔴 | N | N | N | N | N | P1 | No document model or endpoint |
| 23 | Students | Student enrollment | ✅ | Y | Y | Y | Y | Y | P0 | StudentLevel per academic year |
| 24 | Students | Student academic history | 🟡 | Y | P | P | Y | N | P2 | AcademicHistory model; limited surfacing |
| 25 | Students | Search / filtering | 🟠 | ? | Y | ? | — | N | P1 | Search param not confirmed in StudentListView |
| 26 | Students | Pagination | ✅ | Y | Y | Y | — | Y | P0 | StandardResultsPagination |
| 27 | Students | Status management | ✅ | Y | Y | Y | Y | Y | P1 | active / inactive / graduated / withdrawn / transferred |
| 28 | Students | Student portal account | ✅ | Y | Y | Y | Y | Y | P1 | Bulk portal activation, credentials |
| 29 | Students | Student ID / admission number | 🟡 | P | Y | P | Y | N | P1 | enrollment_id is caller-supplied; no auto-generation |
| 30 | Students | Student transfer | 🟡 | P | N | N | P | N | P2 | Status value only; no transfer workflow |
| 31 | Students | Withdrawal / leaving | 🟡 | P | N | N | P | N | P2 | Status value only; no exit record or clearance |
| 32 | Students | Certificate management | 🔴 | N | N | N | N | N | P1 | See Section Q |

### C. Parent / Family

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 33 | Family | Parent management | 🟡 | Y | N | Y | Y | Y | P1 | CRUD API; no standalone screen, created via wizard |
| 34 | Family | Guardian management | 🟡 | P | P | P | P | P | P2 | Guardian is a Parent with relation_type; no separate model |
| 35 | Family | Parent–student relationships | ✅ | Y | P | Y | Y | Y | P0 | StudentParentRelation |
| 36 | Family | Multiple children | ✅ | Y | Y | Y | Y | Y | P0 | children endpoint and switcher |
| 37 | Family | Parent portal | ✅ | Y | Y | Y | Y | Y | P0 | 8 read endpoints, 52 tests |
| 38 | Family | Parent dashboard | 🟡 | P | Y | P | — | P | P1 | parent-portal root page; not a KPI dashboard |
| 39 | Family | Parent notifications | 🟡 | P | Y | Y | Y | Y | P1 | Generic notifications; no parent-specific categories |
| 40 | Family | Parent attendance view | ✅ | Y | Y | Y | Y | Y | P0 | Child attendance endpoint |
| 41 | Family | Parent exam / result view | ✅ | Y | Y | Y | Y | Y | P0 | Results, report card, upcoming exams |
| 42 | Family | Parent fee view | ✅ | Y | Y | Y | Y | Y | P0 | Child fees endpoint |

### D. Admissions

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 43 | Admissions | Admission enquiry | 🔴 | N | N | N | N | N | P1 | No enquiry model |
| 44 | Admissions | Applicant management | 🔴 | N | N | N | N | N | P0 | No applicant entity; enrollment creates students directly |
| 45 | Admissions | Online admission application | 🔴 | N | N | N | N | N | P1 | Public site only supports school signup |
| 46 | Admissions | Admission form | 🟡 | P | Y | Y | Y | Y | P1 | Admin enrollment wizard exists, not applicant-facing |
| 47 | Admissions | Admission documents | 🔴 | N | N | N | N | N | P2 | No document workflow |
| 48 | Admissions | Admission verification | 🔴 | N | N | N | N | N | P2 | No verification step |
| 49 | Admissions | Entrance test | 🔴 | N | N | N | N | N | P3 | Not present |
| 50 | Admissions | Admission interview | 🔴 | N | N | N | N | N | P3 | Not present |
| 51 | Admissions | Approval / rejection | 🔴 | N | N | N | N | N | P1 | No application state machine |
| 52 | Admissions | Applicant → student conversion | 🔴 | N | N | N | N | N | P1 | Depends on 44 |
| 53 | Admissions | Admission number generation | 🟡 | P | Y | P | Y | N | P1 | Caller-supplied enrollment_id |
| 54 | Admissions | Admission reports | 🔴 | N | N | N | N | N | P2 | Not present |

### E. Academic Management

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 55 | Academics | Academic year | 🟡 | P | N | N | P | N | P1 | Plain string convention; no AcademicYear model |
| 56 | Academics | Levels / classes | ✅ | Y | Y | Y | Y | N | P0 | AcademicLevel under Program |
| 57 | Academics | Sections | ✅ | Y | Y | Y | Y | N | P0 | Section with capacity |
| 58 | Academics | Subjects | ✅ | Y | Y | Y | Y | N | P0 | Subject per level |
| 59 | Academics | Courses | 🟡 | P | N | N | P | N | P2 | Subject serves as course; no catalogue |
| 60 | Academics | Enrollments | ✅ | Y | Y | Y | Y | Y | P0 | StudentLevel |
| 61 | Academics | Teacher assignment | ✅ | Y | Y | Y | Y | N | P0 | SubjectAssignment |
| 62 | Academics | Class–subject mapping | ✅ | Y | Y | Y | Y | N | P0 | Via SubjectAssignment |
| 63 | Academics | Academic promotion | ✅ | Y | Y | Y | Y | Y | P0 | Candidates, preview, execute, reverse |
| 64 | Academics | Academic history | 🟡 | P | P | P | Y | N | P2 | PromotionRecord timeline; no transcript view |
| 65 | Academics | Academic calendar | 🔴 | N | N | N | N | N | P1 | No calendar entity |
| 66 | Academics | School events calendar | 🔴 | N | N | N | N | N | P2 | Not present |

### F. Timetable

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 67 | Timetable | Timetable | ✅ | Y | Y | Y | Y | Y | P0 | TimetableEntry per section, weekday |
| 68 | Timetable | Period management | ✅ | Y | Y | Y | Y | Y | P0 | Period model and CRUD |
| 69 | Timetable | Teacher timetable | ✅ | Y | Y | Y | Y | Y | P0 | Instructor timetable endpoint |
| 70 | Timetable | Student / class timetable | ✅ | Y | Y | Y | Y | Y | P0 | Section timetable; child timetable for parents |
| 71 | Timetable | Room allocation | ✅ | Y | Y | Y | Y | Y | P1 | Room FK on entry |
| 72 | Timetable | Teacher conflict detection | 🟠 | ? | ? | ? | — | Y | P0 | Not confirmed in service layer this pass |
| 73 | Timetable | Room conflict detection | 🟠 | ? | ? | ? | — | Y | P1 | Not confirmed in service layer this pass |
| 74 | Timetable | Subject scheduling | ✅ | Y | Y | Y | Y | Y | P0 | Entries carry subject |
| 75 | Timetable | Timetable publishing | 🔴 | N | N | N | N | N | P2 | No draft/published state |
| 76 | Timetable | Timetable PDF / print | 🔴 | N | N | N | — | N | P3 | Not present |

### G. Attendance

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 77 | Attendance | Attendance sessions | ✅ | Y | Y | Y | Y | Y | P0 | One per section per date |
| 78 | Attendance | Student attendance | ✅ | Y | Y | Y | Y | Y | P0 | Bulk mark |
| 79 | Attendance | Attendance records | ✅ | Y | Y | Y | Y | Y | P0 | StudentAttendance |
| 80 | Attendance | Attendance reports | ✅ | Y | Y | Y | — | Y | P1 | Below-threshold, tenant summary |
| 81 | Attendance | Attendance statistics | ✅ | Y | Y | Y | — | Y | P1 | Counts and percentages |
| 82 | Attendance | Monthly attendance | ✅ | Y | P | Y | — | Y | P1 | Month/year filter on section summary |
| 83 | Attendance | Attendance percentage | ✅ | Y | Y | Y | Y | Y | P0 | Configurable status weights |
| 84 | Attendance | Late / absent tracking | ✅ | Y | Y | Y | Y | Y | P0 | Statuses present/absent/late/half_day/leave |
| 85 | Attendance | Staff attendance | ✅ | Y | Y | Y | Y | Y | P1 | StaffAttendance, bulk mark |
| 86 | Attendance | Correction workflow | 🟡 | P | P | P | P | Y | P2 | Edit and lock exist; no approval flow |
| 87 | Attendance | Attendance notifications | 🔴 | N | N | N | — | N | P2 | No absence alerts to parents |

### H. Examinations / Results

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 88 | Exams | Examination management | ✅ | Y | Y | Y | Y | Y | P0 | Types and examinations CRUD |
| 89 | Exams | Exam schedule | ✅ | Y | Y | Y | Y | Y | P0 | Per subject and section |
| 90 | Exams | Exam subjects | ✅ | Y | Y | Y | Y | Y | P0 | Via schedules |
| 91 | Exams | Mark entry | ✅ | Y | Y | Y | Y | Y | P0 | Bulk marks with roster checks |
| 92 | Exams | Exam marks | ✅ | Y | Y | Y | Y | Y | P0 | ExamMark, absence distinct from null |
| 93 | Exams | Result calculation | ✅ | Y | — | Y | Y | Y | P0 | Bulk calculation (Phase 9G) |
| 94 | Exams | Exam results | ✅ | Y | Y | Y | Y | Y | P0 | ExamResult snapshot |
| 95 | Exams | Result publication | ✅ | Y | Y | Y | Y | Y | P0 | Atomic publish, notifications queued |
| 96 | Exams | Published result access | ✅ | Y | Y | Y | Y | Y | P0 | Gated to student and parent |
| 97 | Exams | Student result view | ✅ | Y | Y | Y | Y | Y | P0 | StudentResultsView |
| 98 | Exams | Parent result view | ✅ | Y | Y | Y | Y | Y | P0 | ChildResultsView |
| 99 | Exams | Result reports | 🟡 | Y | P | Y | — | Y | P1 | Below-passing only |
| 100 | Exams | Report card generation | 🟡 | Y | P | Y | — | Y | P1 | Report-card view is data, not a printable card |
| 101 | Exams | Grade configuration | ✅ | Y | Y | Y | Y | Y | P1 | GradeBoundary per academic year |
| 102 | Exams | Rank / position | 🔴 | N | N | N | N | N | P1 | Not computed |
| 103 | Exams | Transcript | 🔴 | N | N | N | N | N | P2 | Not present |

### I. Fees / Finance

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 104 | Fees | Fee structure | ✅ | Y | Y | Y | Y | Y | P0 | FeeHead, FeeStructure |
| 105 | Fees | Student fee allocation | ✅ | Y | Y | Y | Y | Y | P0 | Assign fee, snapshot level/section |
| 106 | Fees | Student fees | ✅ | Y | Y | Y | Y | Y | P0 | Per-student fee rows |
| 107 | Fees | Payment management | ✅ | Y | Y | Y | Y | Y | P0 | Record payment, race-safe locking |
| 108 | Fees | Payment history | ✅ | Y | Y | Y | Y | Y | P1 | Per-student payments |
| 109 | Fees | Outstanding fees | ✅ | Y | Y | Y | Y | Y | P0 | Paginated report with total |
| 110 | Fees | Fee reports | 🟡 | Y | Y | Y | — | Y | P1 | Outstanding only |
| 111 | Fees | Online payment (fees) | 🔴 | N | N | N | — | — | P1 | eSewa exists for school signup only |
| 112 | Fees | Payment gateway | 🟡 | P | N | P | P | P | P1 | payments app; fixed amount, signup-only |
| 113 | Fees | Refund management | 🟡 | P | P | P | Y | Y | P1 | Reversal creates offsetting payment; no refund disbursement |
| 114 | Fees | Discounts / concessions | ✅ | Y | Y | Y | Y | Y | P1 | discount_amount and reason |
| 115 | Fees | Scholarships | 🔴 | N | N | N | N | N | P2 | Not present |
| 116 | Fees | Installment plans | 🔴 | N | N | N | N | N | P1 | Single due date only |
| 117 | Fees | Receipts | ✅ | Y | Y | Y | Y | Y | P1 | receipt_number and receipt view |
| 118 | Fees | Financial reports | 🟡 | P | P | P | — | Y | P1 | Outstanding only; no collections or daily close |

### J. LMS / Course Content

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 119 | LMS | Course content | ✅ | Y | Y | Y | Y | Y | P0 | Notes, documents, videos, links |
| 120 | LMS | Lessons | 🟡 | P | P | P | P | N | P2 | Content items, no ordered lesson sequence |
| 121 | LMS | Assignments | ✅ | Y | Y | Y | Y | Y | P0 | Targeted, due dates, points |
| 122 | LMS | Student submissions | ✅ | Y | Y | Y | Y | Y | P0 | File, text, or link |
| 123 | LMS | Assignment feedback | ✅ | Y | Y | Y | Y | P | P1 | Score and feedback fields |
| 124 | LMS | Assignment grading | ✅ | Y | Y | Y | Y | P | P0 | Grade action |
| 125 | LMS | Content access control | ✅ | Y | Y | Y | Y | Y | P0 | Targeting in queryset |
| 126 | LMS | Teacher content management | ✅ | Y | Y | Y | Y | P | P0 | Manage screen |
| 127 | LMS | Student content access | ✅ | Y | Y | Y | Y | Y | P0 | my_content endpoint |
| 128 | LMS | Course progress | 🔴 | N | N | N | N | N | P2 | No progress tracking |
| 129 | LMS | Online quizzes | 🔴 | N | N | N | N | N | P1 | No quiz model; only assignment types |
| 130 | LMS | Learning materials | ✅ | Y | Y | Y | Y | Y | P1 | Materials page |

### K. Library

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 131 | Library | Library management | 🔴 | N | N | N | N | N | P1 | Only a fee head name "Library" exists |
| 132 | Library | Book catalogue | 🔴 | N | N | N | N | N | P1 | Not present |
| 133 | Library | Book categories | 🔴 | N | N | N | N | N | P1 | Not present |
| 134 | Library | Authors / publishers | 🔴 | N | N | N | N | N | P1 | Not present |
| 135 | Library | Book copies | 🔴 | N | N | N | N | N | P1 | Not present |
| 136 | Library | Barcode / ISBN | 🔴 | N | N | N | N | N | P2 | Not present |
| 137 | Library | Book issue | 🔴 | N | N | N | N | N | P1 | Not present |
| 138 | Library | Book return | 🔴 | N | N | N | N | N | P1 | Not present |
| 139 | Library | Book renewal | 🔴 | N | N | N | N | N | P2 | Not present |
| 140 | Library | Due date tracking | 🔴 | N | N | N | N | N | P1 | Not present |
| 141 | Library | Library fine | 🔴 | N | N | N | N | N | P2 | Not present |
| 142 | Library | Borrowing history | 🔴 | N | N | N | N | N | P2 | Not present |

### L. Transport

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 143 | Transport | Transport management | 🔴 | N | N | N | N | N | P2 | Only a fee head name "Transport" |
| 144 | Transport | Vehicles | 🔴 | N | N | N | N | N | P2 | Not present |
| 145 | Transport | Drivers | 🔴 | N | N | N | N | N | P2 | Not present |
| 146 | Transport | Routes | 🔴 | N | N | N | N | N | P2 | Not present |
| 147 | Transport | Stops | 🔴 | N | N | N | N | N | P2 | Not present |
| 148 | Transport | Student route assignment | 🔴 | N | N | N | N | N | P2 | Not present |
| 149 | Transport | Transport fees | 🟡 | P | P | P | Y | N | P2 | Generic fee structure can carry it; no route linkage |
| 150 | Transport | Vehicle capacity | 🔴 | N | N | N | N | N | P3 | Not present |
| 151 | Transport | Driver documents | 🔴 | N | N | N | N | N | P3 | Not present |
| 152 | Transport | GPS tracking | 🔵 | N | N | N | N | N | P3 | FUTURE — hardware and third-party dependency |

### M. HR Management

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 153 | HR | Employee management | ✅ | Y | Y | Y | Y | N | P0 | StaffMember CRUD, onboarding |
| 154 | HR | Departments | 🟡 | P | N | N | P | N | P1 | department is free text |
| 155 | HR | Designations | 🟡 | P | N | N | P | N | P1 | designation is free text |
| 156 | HR | Employee documents | 🔴 | N | N | N | N | N | P1 | Not present |
| 157 | HR | Qualifications | 🟡 | P | Y | Y | Y | N | P2 | Free-text qualification field |
| 158 | HR | Experience | 🟡 | P | Y | Y | Y | N | P2 | experience_years only |
| 159 | HR | Joining / exit | 🟡 | P | P | P | P | N | P2 | joining_date; no exit or separation record |
| 160 | HR | Leave management | 🔴 | N | N | N | N | N | P0 | No leave request model; "leave" is only an attendance status |
| 161 | HR | Leave approval | 🔴 | N | N | N | N | N | P0 | Depends on 160 |
| 162 | HR | Leave balance | 🔴 | N | N | N | N | N | P1 | Depends on 160 |
| 163 | HR | Employee attendance | ✅ | Y | Y | Y | Y | Y | P1 | StaffAttendance |

### N. Payroll

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 164 | Payroll | Salary structure | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 165 | Payroll | Allowances | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 166 | Payroll | Deductions | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 167 | Payroll | Payroll processing | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 168 | Payroll | Payslips | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 169 | Payroll | Tax / statutory | 🔵 | N | N | N | N | N | P3 | FUTURE — jurisdiction-specific |
| 170 | Payroll | Payroll reports | 🔵 | N | N | N | N | N | P3 | FUTURE |

### O. Inventory / Assets

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 171 | Inventory | Inventory management | 🔴 | N | N | N | N | N | P2 | Not present |
| 172 | Inventory | Stock items | 🔴 | N | N | N | N | N | P2 | Not present |
| 173 | Inventory | Stock in / out | 🔴 | N | N | N | N | N | P2 | Not present |
| 174 | Inventory | Suppliers | 🔴 | N | N | N | N | N | P3 | Not present |
| 175 | Inventory | Purchase orders | 🔴 | N | N | N | N | N | P3 | Not present |
| 176 | Assets | Assets | 🔴 | N | N | N | N | N | P2 | Not present |
| 177 | Assets | Asset assignment | 🔴 | N | N | N | N | N | P3 | Not present |
| 178 | Assets | Asset maintenance | 🔴 | N | N | N | N | N | P3 | Not present |
| 179 | Assets | Asset disposal | 🔴 | N | N | N | N | N | P3 | Not present |

### P. Communication

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 180 | Communication | Notifications | ✅ | Y | Y | Y | Y | Y | P0 | In-app inbox |
| 181 | Communication | Announcements | 🔴 | N | N | N | N | N | P1 | No broadcast entity |
| 182 | Communication | School notices | 🔴 | N | N | N | N | N | P1 | Not present |
| 183 | Communication | Targeted communication | 🟡 | P | N | N | Y | Y | P1 | notify_many supports recipients; no admin UI |
| 184 | Communication | Parent communication | 🟡 | P | N | N | Y | Y | P1 | Result emails to parents only |
| 185 | Communication | Teacher communication | 🔴 | N | N | N | N | N | P2 | Not present |
| 186 | Communication | Scheduled announcements | 🔴 | N | N | N | N | N | P2 | Not present |
| 187 | Communication | SMS integration | 🔵 | N | N | N | N | N | P3 | FUTURE — provider contract |
| 188 | Communication | WhatsApp integration | 🔵 | N | N | N | N | N | P3 | FUTURE — provider contract |

### Q. Certificates / Documents

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 189 | Documents | Document management | 🔴 | N | N | N | N | N | P1 | Only ad-hoc FileFields |
| 190 | Documents | Student documents | 🔴 | N | N | N | N | N | P1 | Not present |
| 191 | Documents | Staff documents | 🔴 | N | N | N | N | N | P1 | Not present |
| 192 | Certificates | Certificate templates | 🔴 | N | N | N | N | N | P1 | Not present |
| 193 | Certificates | Bonafide certificate | 🔴 | N | N | N | N | N | P1 | Not present |
| 194 | Certificates | Transfer certificate | 🔴 | N | N | N | N | N | P1 | Depends on 30 |
| 195 | Certificates | Character certificate | 🔴 | N | N | N | N | N | P2 | Not present |
| 196 | Certificates | Study certificate | 🔴 | N | N | N | N | N | P2 | Not present |
| 197 | Certificates | Certificate numbering | 🔴 | N | N | N | N | N | P2 | Not present |
| 198 | Certificates | Certificate verification | 🔴 | N | N | N | N | N | P3 | Not present |

### R. Student Activities

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 199 | Activities | Sports | 🔴 | N | N | N | N | N | P3 | Not present |
| 200 | Activities | Clubs | 🔴 | N | N | N | N | N | P3 | Not present |
| 201 | Activities | Competitions | 🔴 | N | N | N | N | N | P3 | Not present |
| 202 | Activities | Events | 🔴 | N | N | N | N | N | P3 | Not present |
| 203 | Activities | Achievements | 🔴 | N | N | N | N | N | P3 | Not present |
| 204 | Activities | Awards | 🔴 | N | N | N | N | N | P3 | Not present |
| 205 | Activities | Participation certificates | 🔴 | N | N | N | N | N | P3 | Depends on 192 |

### S. Health / Medical

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 206 | Health | Student medical profile | 🔴 | N | N | N | N | N | P2 | Not present |
| 207 | Health | Emergency contact | 🟡 | P | P | P | P | N | P1 | Parent records serve as contacts; no dedicated emergency contact |
| 208 | Health | Allergies | 🔴 | N | N | N | N | N | P2 | Not present |
| 209 | Health | Medical incidents | 🔴 | N | N | N | N | N | P2 | Not present |
| 210 | Health | Health checkups | 🔴 | N | N | N | N | N | P3 | Not present |
| 211 | Health | Vaccination records | 🔴 | N | N | N | N | N | P3 | Not present |

### T. Campus / Facility

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 212 | Campus | Campus management | 🔴 | N | N | N | N | N | P3 | Not present |
| 213 | Campus | Buildings | 🔴 | N | N | N | N | N | P3 | Not present |
| 214 | Campus | Floors | 🔴 | N | N | N | N | N | P3 | Not present |
| 215 | Campus | Rooms | 🟡 | P | P | P | Y | Y | P2 | timetable.Room exists; not a campus entity |
| 216 | Campus | Laboratories | 🔴 | N | N | N | N | N | P3 | Not present |
| 217 | Campus | Auditorium | 🔴 | N | N | N | N | N | P3 | Not present |
| 218 | Campus | Facility booking | 🔴 | N | N | N | N | N | P3 | Not present |

### U. Analytics / BI

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 219 | Analytics | Standard reports | 🟡 | P | P | P | — | Y | P1 | Per-module reports only |
| 220 | Analytics | Dashboard analytics | 🟡 | Y | Y | Y | — | Y | P1 | Single KPI summary, no drill-down |
| 221 | Analytics | Student analytics | 🔴 | N | N | N | N | N | P2 | Not present |
| 222 | Analytics | Attendance analytics | 🟡 | P | P | P | — | Y | P2 | Reports, no trends or charts |
| 223 | Analytics | Exam analytics | 🔴 | N | N | N | N | N | P2 | Only below-passing report |
| 224 | Analytics | Fee analytics | 🟡 | P | P | P | — | Y | P2 | Outstanding report only |
| 225 | Analytics | Teacher analytics | 🔴 | N | N | N | N | N | P3 | Not present |
| 226 | Analytics | Predictive analytics | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 227 | Analytics | AI analytics | 🔵 | N | N | N | N | N | P3 | FUTURE |

### V. External Integrations

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 228 | Integrations | Email | ✅ | Y | — | — | Y | Y | P0 | Outbox plus SMTP |
| 229 | Integrations | Redis | 🟡 | P | — | — | — | — | P1 | Broker only |
| 230 | Integrations | Celery | 🟡 | Y | — | — | — | P | P1 | Tasks exist; orchestration missing |
| 231 | Integrations | Payment gateway | 🟡 | P | P | P | P | P | P1 | eSewa, signup only |
| 232 | Integrations | SMS provider | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 233 | Integrations | WhatsApp | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 234 | Integrations | Google Calendar | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 235 | Integrations | Google Workspace | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 236 | Integrations | Microsoft 365 | 🔵 | N | N | N | N | N | P3 | FUTURE |
| 237 | Integrations | Biometric attendance | 🔵 | N | N | N | N | N | P3 | FUTURE — attendance models state V1 excludes it |
| 238 | Integrations | Accounting software | 🔵 | N | N | N | N | N | P3 | FUTURE |

### W. Developer / Operations

| # | Module | Feature | Status | B | F | A | D | T | Priority | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 239 | DevOps | API architecture | ✅ | Y | — | Y | — | Y | P0 | DRF, consistent prefixes |
| 240 | DevOps | API authentication | ✅ | Y | — | Y | — | Y | P0 | Cookie JWT |
| 241 | DevOps | API permissions | ✅ | Y | — | Y | — | Y | P0 | HasPermission |
| 242 | DevOps | API pagination | 🟡 | Y | Y | Y | — | Y | P1 | Mixed page sizes across apps |
| 243 | DevOps | API filtering | 🟡 | P | P | P | — | Y | P2 | Only some ViewSets |
| 244 | DevOps | API validation | ✅ | Y | Y | Y | — | Y | P1 | Serializers and service rules |
| 245 | DevOps | Audit logging | 🟡 | Y | N | Y | Y | Y | P1 | No viewer screen |
| 246 | DevOps | Background processing | 🟡 | Y | — | — | — | P | P1 | Worker not orchestrated |
| 247 | DevOps | Error handling | 🟡 | Y | Y | Y | — | P | P1 | `error` and `detail` keys used inconsistently |
| 248 | DevOps | Database optimization | ✅ | Y | — | — | Y | Y | P1 | Indexes plus Phase 9 work |
| 249 | DevOps | N+1 query optimization | 🟡 | Y | — | — | — | Y | P1 | Major paths fixed; notification fan-out and seed loop open |
| 250 | DevOps | Automated testing | 🟡 | Y | P | — | — | Y | P1 | 0 tests in academics, staff, profiles, organizations; slow suite |
| 251 | DevOps | Production monitoring | 🔴 | N | N | N | — | N | P1 | No monitoring configuration found |
| 252 | DevOps | Backup / recovery | 🟠 | ? | — | — | — | — | P1 | Not in repo; infrastructure concern |
| 253 | DevOps | CI/CD | 🟠 | ? | — | — | — | — | P1 | Not confirmed in this pass |
| 254 | DevOps | API documentation | 🟡 | P | — | P | — | N | P2 | drf-spectacular installed; schema not verified |
| 255 | DevOps | Developer documentation | 🟡 | P | — | — | — | — | P2 | Agent and guide files exist; no full API reference in repo |

**Matrix totals (counted from the 255 rows above):** ✅ Implemented 83 · 🟡 Partial 55 · 🔴 Missing 93 · 🟠 Needs verification 5 · 🔵 Future 19 · **Total 255**.

---

## 4. Module-by-Module Analysis

### Student Management
- **Overall:** 🟡 PARTIALLY IMPLEMENTED (core strong; documents, admissions link, transfer and certificates missing)
- **Backend:** Student, StudentLevel, AcademicHistory, PromotionRecord; enrollment, portal activation, promotion.
- **Frontend:** list, edit, admissions wizard, promotion, portal-access screens.
- **API:** full list/detail/enroll/credentials/portal endpoints.
- **Database:** Student has a status-and-date index; enrollment uniqueness per academic year.
- **Testing:** 85 tests in students.
- **Missing:** student documents, photo upload verification, enrollment-number generation, transfer and withdrawal workflow, certificates.
- **Next step:** add a student documents entity and enrollment-number sequence before admissions.

### Parent / Family
- **Overall:** ✅ IMPLEMENTED for the portal; 🟡 for management UI.
- **Backend:** Parent, StudentParentRelation, parent_portal with eight read endpoints.
- **Frontend:** full parent-portal route set.
- **Testing:** 52 parent_portal tests, 20 families tests.
- **Missing:** a standalone family management screen; parent-specific notification categories.

### Staff / HR
- **Overall:** 🟡 PARTIALLY IMPLEMENTED (people records and attendance exist; leave, departments, documents missing).
- **Backend:** StaffMember, Instructor, onboarding and activation endpoints, StaffAttendance.
- **Frontend:** staff, onboarding, edit, instructors, recruit, faculty onboarding, portal-access.
- **Testing:** **0 tests in staff.**
- **Missing:** leave request, approval, balance; departments and designations as entities; employee documents; separation record.

### Academic Management
- **Overall:** ✅ IMPLEMENTED for structure; 🟡 for calendar and academic year.
- **Backend:** Program, AcademicLevel, Section, Subject, SubjectAssignment.
- **Frontend:** single tabbed academics page.
- **Testing:** **0 tests in academics.**
- **Missing:** AcademicYear model (currently a string convention), academic calendar, school events.

### Timetable
- **Overall:** ✅ IMPLEMENTED for entries and views; 🟠 for conflict detection (not confirmed); 🔴 for publishing and print.
- **Backend:** Period, Room, TimetableEntry, TimetableSubstitution, with view-level access checks.
- **Frontend:** timetable, my-schedule, substitutions.
- **Testing:** 44 tests.
- **Missing:** confirmed teacher and room conflict checks at service level, draft and publish state, printable timetable.

### Attendance
- **Overall:** ✅ IMPLEMENTED (strongest operational module with staff attendance).
- **Backend:** AttendanceSession, StudentAttendance, StaffAttendance, AttendanceSettings, reports.
- **Frontend:** mark, history, reports, staff, settings.
- **Testing:** 40 tests.
- **Missing:** absence notifications to parents, correction approval, biometric (FUTURE).

### Examinations / Results
- **Overall:** ✅ IMPLEMENTED for core cycle; 🟡 for report card and reports; 🔴 for rank and transcript.
- **Backend:** ExamType, Examination, ExamSchedule, ExamMark, ExamResult (immutable), GradeBoundary, bulk calculation.
- **Frontend:** examinations, marks, results, grading.
- **Testing:** 73 tests.
- **Missing:** rank and position, transcript, printable report card, exam analytics.

### Fees / Finance
- **Overall:** ✅ IMPLEMENTED for the fee cycle; 🟡 for gateway, refunds and reporting; 🔴 for scholarships and installments.
- **Backend:** FeeHead, FeeStructure, StudentFee, Payment, PaymentAllocation, reversal, outstanding report; separate payments app for signup.
- **Frontend:** collect, structures, reports, my-fees.
- **Testing:** 95 tests in fees (strongest test coverage).
- **Missing:** online fee payment, scholarships, installment plans, refund disbursement workflow, collection and daily-close reports.

### LMS / Course Content
- **Overall:** ✅ IMPLEMENTED for assignments and content; 🔴 for quizzes and progress.
- **Backend:** CourseContent, Assignment, AssignmentSubmission, SubjectEnrollment.
- **Frontend:** materials, manage, assignments, grading.
- **Testing:** **4 tests** — thin relative to the feature.
- **Missing:** quizzes, course progress, ordered lessons. Also a dead `bulk_grade` reference.

### Library, Transport, Inventory, Assets, Campus, Health, Activities, Payroll
- **Overall:** 🔴 MISSING (Payroll and GPS, SMS, WhatsApp, biometric and cloud integrations are 🔵 FUTURE).
- **Evidence:** keyword sweeps across backend and frontend returned no workflow. The only "Library" in the frontend is a Lucide icon on the academics page and a content-library phrase in a hook comment. "Transport" and "Library" exist only as fee-head seed names in `fees/signals.py`.

### Admissions
- **Overall:** 🔴 MISSING as an applicant workflow.
- **Evidence:** the `students/admissions` route is an admin enrollment wizard, not an applicant pipeline. The public site supports school signup only.

### Communication
- **Overall:** 🟡 PARTIALLY IMPLEMENTED.
- **Backend:** in-app notifications (synchronous), email outbox, result-published emails.
- **Missing:** announcements, school notices, scheduled broadcasts, admin targeting UI.

### Certificates / Documents
- **Overall:** 🔴 MISSING.
- **Evidence:** only ad-hoc FileFields exist (profile image, institution logo/banner, course content, submissions).

### Analytics / BI
- **Overall:** 🟡 PARTIALLY IMPLEMENTED.
- **Backend:** dashboard summary (one endpoint, seven KPI groups), attendance, exam and fee reports.
- **Missing:** drill-down analytics, trends, charts, exam and teacher analytics; AI and predictive are FUTURE.

### Platform / Operations
- **Overall:** ✅ strong on auth, tenancy, RBAC, outbox; 🟡 on throttling, audit viewer, error-key consistency, worker orchestration, test breadth; 🔴 on monitoring; 🟠 on backup and CI/CD (not verified).

---

## 5. Current vs Missing Features

| Current (usable) | Missing (should exist) |
|---|---|
| Tenant provisioning, login, RBAC, password reset | Applicant pipeline, admissions workflow |
| Student records, enrollment, portal accounts | Student documents, transfer certificate, enrollment numbering |
| Parent portal (attendance, results, fees, timetable) | Parent-facing announcements |
| Timetable, sections, subjects, teacher assignments | Academic calendar, timetable publishing |
| Attendance (student and staff), reports | Absence alerts, correction approval |
| Exams, marks, results, publication, grading | Rank, transcript, printable report card |
| Fees, payments, reversals, outstanding report | Online fee payment, scholarships, installments |
| Assignments, submissions, grading, content access | Quizzes, progress tracking |
| In-app notifications, email outbox | Announcements, notices, SMS/WhatsApp (FUTURE) |
| Promotion with preview and reversal | Leave, library, transport, inventory, health, activities |

---

## 6. Top 20 Gaps

Ranked by business importance, dependency position, ERP necessity, and user value.

| Rank | Feature | Current Status | Priority | Reason |
|---|---|---|---|---|
| 1 | Admissions (applicant pipeline) | 🔴 Missing | P0 | Student lifecycle begins here; blocks clean student creation |
| 2 | Leave management (request, approval, balance) | 🔴 Missing | P0 | Daily HR need; blocks attendance-leave reconciliation |
| 3 | Announcements and school notices | 🔴 Missing | P1 | Highest-frequency parent and staff communication need |
| 4 | Online fee payment (students/parents) | 🟡 Partial (signup only) | P1 | Direct revenue and collection impact |
| 5 | Installment plans and scholarships | 🔴 Missing | P1 | Common Indian private-school fee practice |
| 6 | Student documents and certificates (TC, bonafide) | 🔴 Missing | P1 | Frequent administrative requests; depends on transfer workflow |
| 7 | Student transfer and withdrawal workflow | 🟡 Partial | P1 | Status values exist without the process |
| 8 | Academic year as a real entity | 🟡 Partial | P1 | Every module relies on a string convention; risk of drift |
| 9 | Rank and transcript | 🔴 Missing | P1 | Expected in exam results cycle |
| 10 | Library (catalogue, issue, return, fines) | 🔴 Missing | P1 | Common school ERP module |
| 11 | Quizzes and course progress | 🔴 Missing | P1 | Expected for LMS credibility |
| 12 | Calendar and events | 🔴 Missing | P1 | Drives timetable, exams and announcements |
| 13 | Automated test coverage for academics, staff, profiles, organizations | 🟡 Partial (zero tests) | P1 | Regression risk in core structure |
| 14 | Audit log viewer | 🟡 Partial | P1 | Backend exists; admins cannot inspect it |
| 15 | Celery worker/beat orchestration and monitoring | 🟡 Partial / 🔴 monitoring | P1 | Email delivery depends on it in production |
| 16 | Rate limiting beyond auth endpoints | 🟡 Partial | P1 | Only six scopes throttled |
| 17 | Consistent API error shape | 🟡 Partial | P1 | Frontend must handle two keys |
| 18 | Transport (routes, stops, assignments) | 🔴 Missing | P2 | Fee head exists without the module |
| 19 | Inventory and assets | 🔴 Missing | P2 | Operational completeness |
| 20 | Health records (medical profile, allergies, emergency contact) | 🔴 Missing | P2 | Safety and compliance for schools |

---

## 7. Dependency Map

```
Admission (applicant) ─→ Student ─→ Enrollment (StudentLevel) ─→ Academic (Level/Section/Subject)
                                                                        ↓
Timetable (Period/Room/Entry) ─→ Attendance (Session/Record) ─→ Examination (Schedule/Mark/Result)
                                                                        ↓
                                                              Promotion (PromotionRecord)
                                                                        ↓
                                                            Certificates (TC depends on withdrawal)

Student ─→ Fee structure ─→ StudentFee ─→ Payment ─→ Allocation ─→ Receipt ─→ Financial reports
                                     ↘ Scholarship / Installment (new, modifies StudentFee)
                                     ↘ Transport fee (depends on Transport routes)

Staff ─→ Leave request ─→ Approval ─→ Attendance reconciliation ─→ Payroll (FUTURE)

Academic year (currently string) ─→ every module above (promotion, fees, exams, timetable)

Notifications / Outbox ─→ Announcements, leave decisions, fee reminders, absence alerts
Parent portal ─→ depends on Family, Attendance, Exams, Fees, Timetable (all present)
Library ─→ Student and Staff (borrowers); fines feed Fees
Transport ─→ Student (assignment), Fees (transport fee), Staff (drivers)
```

**Key dependency observations**
- Admissions must precede clean enrollment; currently enrollment creates students directly.
- Leave must be modelled before attendance can distinguish approved leave from absence.
- Academic year as a real entity is a prerequisite for reliable promotion, fee cycles, and reporting across years.
- Certificates depend on withdrawal or transfer state, which is currently only a status value.

---

## 8. Recommended Roadmap

### Phase 0 — Stabilize current code (before new modules)

| # | Item | Why | Evidence |
|---|---|---|---|
| 0.1 | Fail closed when `ESEWA_CLIENT_SECRET` is empty | An empty HMAC key is a predictable secret; misconfiguration would let forged callbacks verify | `config/settings.py:321` default `""`; `payments/views.py` signature check |
| 0.2 | Replace fixed payment amount "500" or gate the flow | Hard-coded amount in `InitPaymentView` | `payments/views.py` comment "Fixed amount for now" |
| 0.3 | Remove or relocate the committed student PDF | Personal or project file in source tree | `backend/submissions/2026/01/Fianl_Year_Project.pdf` |
| 0.4 | Add tests for academics, staff, profiles, organizations | Core structure has zero test coverage | Test counts above |
| 0.5 | Remove dead `bulk_grade` reference | Misleading permission branch | `course_content/views.py` `get_permissions` |
| 0.6 | Clarify or remove seed fee heads "Transport" and "Library" | Creates false impression of modules | `fees/signals.py` |
| 0.7 | Standardize error response key | Frontend handles `error` and `detail` inconsistently | Section 20 of the API docs |
| 0.8 | Fix stale docstring in `recover_stale_outbox_events` | States Beat is not wired, but it is | `notifications/tasks.py` |
| 0.9 | Confirm Celery worker and beat run mode in deployment | Email delivery depends on it | No compose or Procfile entry found |
| 0.10 | Resolve N+1 in publish notification fan-out (scoped) | Known open item; scales with students | Phase 9G follow-up |

### Phase 1 — Core missing ERP modules (P0/P1)

1. **Academic year entity** — foundation for every year-scoped module. Migrate string-keyed data carefully.
2. **Admissions** — applicant, enquiry, application, document, approval, conversion. Converts into existing Student flow.
3. **Leave management** — request, approve, balance; feeds attendance reconciliation.
4. **Communication** — announcements and notices with audience targeting, built on existing notify_many and outbox.
5. **Student documents and certificates** — document store, bonafide, transfer certificate with numbering and verification.
6. **Online fee payment** — extend the existing eSewa integration from signup to student fee collection, reusing signature verification.
7. **Installments and scholarships** — extend StudentFee; keep allocation rules unchanged.
8. **Library** — catalogue, copies, issue, return, renewal, fines (fines route into Fees).
9. **Calendar and events** — academic calendar feeding timetable and announcements.
10. **Quizzes and progress** — extend course content.

*Order rationale:* academic year and admissions unlock clean data; leave unlocks attendance accuracy; communication and certificates are high-frequency; payments and installments depend on a stable fee model; library and calendar are independent once the foundation exists.

### Phase 2 — Operational modules (P2)

Transport (routes, stops, assignments, fees linked to routes), inventory and assets, campus and rooms as first-class entities, health records (medical profile, allergies, emergency contacts), staff HR depth (departments, designations, documents, separation).

### Phase 3 — Financial expansion

Refund disbursement workflow, collection and daily-close reports, financial reporting extensions, payroll (salary structure, allowances, deductions, payslips) — payroll remains **FUTURE** unless a school requires it.

### Phase 4 — Advanced platform

Activities and awards, analytics and drill-down (student, exam, teacher), mobile experience, SMS and WhatsApp providers, Google and Microsoft integrations, biometric attendance, accounting integration, predictive and AI analytics.

---

## 9. Proposed Architecture for Missing Major Modules

> **PROPOSED** — none of the following exists in the codebase.

| Module | Required new Django app | New models | New serializers | New APIs | New permissions | New frontend routes | Celery | Redis | File storage | Integrations |
|---|---|---|---|---|---|---|---|---|---|---|
| Academic year | Extend `academics` | AcademicYear | Yes | `/api/academics/years/` | `view/manage_academic_year` | `/dashboard/academics/years` | No | No | No | No |
| Admissions | `admissions` (new) | Enquiry, Applicant, Application, ApplicationDocument, EntranceTest, Interview | Yes | `/api/admissions/...` | `view/manage/approve_admission` | `/dashboard/admissions/...` | Optional (notifications) | No | Yes (documents) | No |
| Leave | `leave` (new) | LeaveType, LeaveRequest, LeaveBalance | Yes | `/api/leave/...` | `request_leave`, `approve_leave` | `/dashboard/leave/...` | Optional | No | No | No |
| Communication | Extend `notifications` | Announcement, AnnouncementAudience | Yes | `/api/notifications/announcements/` | `publish_announcement` | `/dashboard/communication` | Yes (scheduled) | Optional | Optional | SMS/WhatsApp FUTURE |
| Documents / Certificates | `documents` (new) | DocumentType, StudentDocument, StaffDocument, CertificateTemplate, IssuedCertificate | Yes | `/api/documents/...` | `view/issue_certificate` | `/dashboard/documents`, `/dashboard/certificates` | Optional (PDF generation) | No | Yes | No |
| Library | `library` (new) | Book, BookCopy, Author, Publisher, Category, BookIssue, LibraryFine | Yes | `/api/library/...` | `manage_library`, `issue_book` | `/dashboard/library/...` | Yes (overdue reminders) | Optional | Optional (covers) | No |
| Transport | `transport` (new) | Vehicle, Driver, Route, Stop, StudentRouteAssignment | Yes | `/api/transport/...` | `manage_transport` | `/dashboard/transport/...` | No | No | Yes (driver docs) | GPS FUTURE |
| Calendar | `calendar` (new) or extend `academics` | CalendarEvent | Yes | `/api/calendar/events/` | `manage_calendar` | `/dashboard/calendar` | No | No | No | Google Calendar FUTURE |
| Health | `health` (new) | MedicalProfile, Allergy, MedicalIncident, EmergencyContact | Yes | `/api/health/...` | `view/manage_medical` (restricted) | `/dashboard/health/...` | No | No | Optional | No |
| Inventory / Assets | `inventory` (new) | Item, StockMovement, Supplier, PurchaseOrder, Asset, AssetAssignment | Yes | `/api/inventory/...`, `/api/assets/...` | `manage_inventory`, `manage_assets` | `/dashboard/inventory`, `/dashboard/assets` | No | No | No | No |
| Activities | `activities` (new) | Club, Event, Competition, Achievement, Award | Yes | `/api/activities/...` | `manage_activities` | `/dashboard/activities/...` | No | No | Optional | No |
| Payroll (FUTURE) | `payroll` (new) | SalaryStructure, Allowance, Deduction, PayrollRun, Payslip | Yes | `/api/payroll/...` | `manage_payroll` (restricted) | `/dashboard/payroll/...` | Yes (run processing) | Optional | Yes (payslips) | Tax rules FUTURE |

---

## 10. Proposed Database Entities

> **PROPOSED MODELS** — do not create without a design review.

```
AcademicYear            (name, start_date, end_date, is_current)
Applicant / Application (applicant identity, status enum, target level, documents)
ApplicationDocument     (application FK, document type, file)
LeaveType / LeaveRequest / LeaveBalance (staff FK, dates, status, approver)
Announcement            (title, body, publish_at, audience FKs, created_by)
DocumentType / StudentDocument / StaffDocument (owner FK, file, expiry)
CertificateTemplate / IssuedCertificate (student FK, number unique per school, issued_by)
Book / BookCopy / Author / Publisher / BookCategory (copy barcode unique)
BookIssue               (copy FK, borrower FK, issued_at, due_at, returned_at)
LibraryFine             (issue FK, amount, status) — posts to fees via existing Payment model
Vehicle / Driver / Route / Stop / StudentRouteAssignment
CalendarEvent           (title, starts_at, ends_at, category, scope)
MedicalProfile / Allergy / MedicalIncident / EmergencyContact (student FK, restricted visibility)
Item / StockMovement / Supplier / PurchaseOrder / Asset / AssetAssignment
Club / Event / Competition / Achievement / Award (student M2M)
SalaryStructure / Allowance / Deduction / PayrollRun / Payslip (FUTURE)
```

**Indexing note:** new tables that filter by school year, student, or status should add composite indexes at creation time, following the existing index patterns in fees and attendance.

---

## 11. Proposed API Surface

> **PROPOSED API — NOT CURRENTLY IMPLEMENTED**

```
Academic year     GET/POST /api/academics/years/   GET/PUT/DELETE /api/academics/years/{id}/
Admissions        GET/POST /api/admissions/enquiries/   GET/POST /api/admissions/applications/
                  POST /api/admissions/applications/{id}/approve/   POST .../reject/   POST .../convert/
Leave             GET/POST /api/leave/requests/   POST /api/leave/requests/{id}/approve/   GET /api/leave/balances/
Communication     GET/POST /api/notifications/announcements/   GET /api/notifications/announcements/{id}/
Documents         GET/POST /api/documents/student/   GET/POST /api/documents/staff/
Certificates      GET/POST /api/documents/certificates/   POST /api/documents/certificates/{id}/issue/
                  GET /api/documents/verify/{number}/
Library           GET/POST /api/library/books/   POST /api/library/issues/   POST /api/library/issues/{id}/return/
                  POST /api/library/issues/{id}/renew/   GET /api/library/fines/
Transport         GET/POST /api/transport/routes/   GET/POST /api/transport/vehicles/
                  POST /api/transport/assignments/
Calendar          GET/POST /api/calendar/events/
Health            GET/PUT /api/health/students/{student_id}/profile/
Inventory         GET/POST /api/inventory/items/   POST /api/inventory/movements/
Assets            GET/POST /api/assets/   POST /api/assets/{id}/assign/
Activities        GET/POST /api/activities/events/   GET/POST /api/activities/achievements/
```

---

## 12. Proposed Frontend Structure

> **PROPOSED — planning only**

| Module | Navigation | Pages | Key forms | Tables / filters | Hooks |
|---|---|---|---|---|---|
| Academic year | Academics → Years | list, detail | year form | years table, current-year badge | `useAcademicYears` |
| Admissions | Admissions (new group) | enquiries, applications, application detail, convert | enquiry form, application form | status filter, search by name | `useAdmissions` |
| Leave | HR → Leave | my leave, approvals, balances | leave request form | status and date filters | `useLeave` |
| Communication | Communication (new) | announcements, compose | announcement form with audience | audience and date filters | `useAnnouncements` |
| Documents / Certificates | Documents (new) | student docs, staff docs, certificates, verify | certificate issue form | owner search, number search | `useDocuments`, `useCertificates` |
| Library | Library (new) | catalogue, issues, fines | book form, issue form | title, ISBN, status filters | `useLibrary` |
| Transport | Transport (new) | routes, vehicles, assignments | route and stop forms | route filter | `useTransport` |
| Calendar | Calendar (new) | month and list views | event form | category filter | `useCalendar` |
| Health | Student → Health | profile tab on student detail | medical profile form | restricted by permission | `useHealth` |
| Inventory / Assets | Operations (new) | stock, assets | item and movement forms | category filter | `useInventory`, `useAssets` |

Follow existing conventions: TableShell for tables, hook-per-domain with array query keys, React Hook Form with Zod for multi-step forms, `Can` component for action-level permissions.

---

## 13. Priority Matrix

| Priority | Items |
|---|---|
| **P0 — Critical** | Admissions (applicant), academic year entity, leave management, fail-closed payment secret (Phase 0.1) |
| **P1 — High** | Communication (announcements), online fee payment, installments and scholarships, student documents and certificates, transfer workflow, rank and transcript, library, calendar, quizzes and progress, test coverage for core apps, audit viewer, Celery orchestration, throttling, error-key consistency |
| **P2 — Medium** | Transport, inventory and assets, campus and rooms, health records, staff HR depth, academic history surfacing, attendance correction approval, timetable publishing, exam and fee analytics |
| **P3 — Low / Future** | Payroll, GPS, SMS, WhatsApp, Google and Microsoft integrations, biometric attendance, accounting integration, AI and predictive analytics, entrance tests and interviews, activities, facility booking |

---

## 14. Build Now / Later / Optional / Future

### Build Now (core ERP)
- Phase 0 stabilization items 0.1–0.8
- Academic year entity
- Admissions (applicant pipeline)
- Leave management
- Announcements and notices
- Student documents and certificates (bonafide, transfer)
- Online fee payment for students and parents
- Installments and scholarships

### Build Later (valuable, can wait)
- Library
- Calendar and events
- Quizzes and course progress
- Rank and transcript
- Inventory and assets
- Transport
- Health records
- Audit log viewer

### Optional (depends on school requirements)
- Campus and facility booking
- Activities, clubs, competitions
- Biometric attendance
- Staff HR depth (exit, separation)
- Teacher communication channel

### Future (intentionally postponed)
- Payroll (jurisdiction-specific)
- GPS tracking
- SMS and WhatsApp providers
- Google and Microsoft 365 integrations
- Accounting software integration
- Predictive and AI analytics

---

## 15. Final Recommendation

### Current Product Maturity (reasoned estimates, not measured metrics)

```text
EduSekai is currently approximately:
Core ERP:            ~65%
Student Management:  ~70%
Academic Management: ~60%
Finance:             ~55%
LMS:                 ~50%
Operations:          ~15%
```

These estimates weigh the implemented workflows above against the checklist. They are judgement calls from code inspection and should be revisited after the Phase 0 items are closed.

### 1. Top 5 Next Modules (ranked)
1. **Admissions** (applicant pipeline) — starts the student lifecycle and removes direct-to-student creation.
2. **Academic year entity** — foundation for reliable year-scoped data.
3. **Leave management** — a daily HR need that also improves attendance accuracy.
4. **Communication** (announcements and notices) — highest-frequency user value using existing notifications and outbox.
5. **Online fee payment** — extends the proven eSewa integration to student fees.

### 2. Top 10 Next Features (ranked)
1. Applicant enquiry and application pipeline
2. Academic year model with migration plan
3. Leave request, approval, and balance
4. Announcements with audience targeting
5. Student fee online payment via eSewa
6. Installment plans on StudentFee
7. Bonafide and transfer certificates with numbering
8. Student document store
9. Rank and transcript on published results
10. Automated tests for academics, staff, profiles, and organizations

### 3. Features We Should NOT Build Yet
- **Payroll** — jurisdiction-specific tax rules and high compliance risk; build only when a school requires it.
- **GPS transport tracking** — hardware and third-party dependencies; no core need.
- **SMS and WhatsApp** — need provider contracts, cost controls, and consent handling first.
- **AI and predictive analytics** — needs clean, complete historical data that the platform does not yet guarantee.
- **Biometric attendance** — hardware integration; the attendance model explicitly excludes it in V1.
- **Accounting software sync** — premature until financial reporting is complete.

### 4. Recommended Development Sequence

```text
Phase 0: Current Stabilization (payment secret, test gaps, stale items)
        ↓
Module 1: Academic Year entity
        ↓
Module 2: Admissions (applicant → student)
        ↓
Module 3: Leave management
        ↓
Module 4: Communication (announcements and notices)
        ↓
Module 5: Student fee online payment, installments, scholarships
```

---

## Appendix — Stabilization Findings Reference

| # | Finding | Location | Severity |
|---|---|---|---|
| A1 | eSewa secret defaults to empty string | `backend/config/settings.py:321` | High (fail-open risk on misconfiguration) |
| A2 | Signup payment amount hard-coded to 500 | `backend/payments/views.py` | Medium |
| A3 | Student PDF committed under submissions | `backend/submissions/2026/01/Fianl_Year_Project.pdf` | Medium (hygiene, possible personal data) |
| A4 | Zero tests in academics, staff, profiles, organizations | test inventory | Medium |
| A5 | Dead `bulk_grade` permission reference | `backend/course_content/views.py` | Low |
| A6 | Transport and Library fee-head names with no module | `backend/fees/signals.py` | Low (misleading) |
| A7 | Mixed `error` / `detail` response keys | multiple views | Low |
| A8 | Stale Beat docstring in outbox sweeper | `backend/notifications/tasks.py` | Low |
| A9 | Access token not revoked on password reset | `backend/accounts/views.py` (documented limitation) | Medium |
| A10 | `active_role` query param trusted for mutations | `backend/roles/permissions.py` (documented concern) | Medium |

---

*This document is an analysis artifact. It makes no code, database, migration, seeder, test, or git changes.*
