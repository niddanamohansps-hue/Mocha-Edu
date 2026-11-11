# EduSekai — System Architecture and Module Workflows

> **Scope:** Reflects the code on `main` as of 11 November 2026. Written from the repository; the workflows marked as browser-tested were also run end to end on a test copy of the system.

## 1. System architecture

```mermaid
flowchart TB
    subgraph Clients["Web clients"]
        Public["EduSekai website<br/>Next.js :3000<br/>School signup and subscription"]
        TenantUI["School app<br/>Next.js :3555<br/>&lt;school&gt;.domain"]
        Apply["Public school pages<br/>apply, admission status, careers"]
    end
    subgraph Backend["Django 5.2 + Django REST Framework"]
        Router["django-tenants<br/>host name selects the school"]
        PublicAPI["Platform APIs<br/>signup, billing, auth"]
        SchoolAPI["School APIs<br/>/api/*"]
    end
    subgraph Data["Data"]
        PG[("PostgreSQL<br/>public schema + one schema per school")]
        Redis[("Redis<br/>cache, metrics, Celery broker")]
    end
    subgraph Workers["Background"]
        Celery["Celery worker + beat<br/>reminders, outbox, reconciliation"]
    end
    subgraph External["External services"]
        Razorpay["Razorpay<br/>school fees + EduSekai subscription"]
        ESewa["eSewa<br/>optional per-school fee gateway"]
        Email["Email"]
        WhatsApp["WhatsApp"]
    end
    Public --> Router
    TenantUI --> Router
    Apply --> Router
    Router --> PublicAPI
    Router --> SchoolAPI
    PublicAPI --> PG
    SchoolAPI --> PG
    SchoolAPI --> Redis
    Celery --> PG
    Celery --> Redis
    SchoolAPI --> Razorpay
    SchoolAPI --> ESewa
    PublicAPI --> Razorpay
    Celery --> Email
    Celery --> WhatsApp
```

**Tenant isolation:** the school's subdomain or domain selects its PostgreSQL schema. All school records live in that schema. User accounts live in the public schema and are linked from school profiles by UUID, not by cross-schema foreign keys.

**Payment gateways:** each school chooses and configures its own fee gateway (Razorpay or eSewa). Schools in India use Razorpay. EduSekai's own subscription billing to schools also uses Razorpay, including autopay mandates and GST invoices.

**Access control:** every school API checks a named permission through roles (`roles` app). The school owner role holds every permission. Platform operators (superusers) see platform-wide tools such as System Health.

**Background jobs (Celery beat):** homework reminders, fee reminders and follow-ups, admission follow-ups and missing documents, pending exam marks, scheduled announcements, notification outbox recovery, online payment and signup payment reconciliation, subscription refresh and a system heartbeat.

## 2. Core school workflow

```mermaid
flowchart LR
    Setup["School setup<br/>years, programs, classes,<br/>sections, subjects"] --> Admit["Admissions<br/>enquiry to student"]
    Setup --> Staff["Staff<br/>onboarding, roles"]
    Admit --> Family["Families<br/>parents linked to students"]
    Staff --> Time["Timetable"]
    Time --> Att["Attendance"]
    Admit --> Fees["Fees<br/>structures, dues, payments"]
    Time --> Learn["Course content,<br/>homework, assignments"]
    Learn --> Exams["Examinations<br/>marks, results, rechecks"]
    Att --> Portal["Parent and student portals"]
    Exams --> Portal
    Fees --> Portal
```

## 3. Module workflows

### 3.1 School signup, login and access

```mermaid
sequenceDiagram
    participant S as School
    participant W as EduSekai website
    participant R as Razorpay
    participant B as Backend
    S->>W: Choose plan and sign up
    W->>R: Pay or set up autopay
    R-->>B: Signed payment result
    B->>B: Create school schema, domain and owner
    S->>B: Owner logs in on the school's domain
    B-->>S: Session with the owner's permissions
```

- Staff, students and parents get logins from **Portal Access**, which can export login details still to be handed out (CSV).
- The **Subscription & Billing** page shows the plan, autopay mandate and GST invoices.

### 3.2 Admissions and student lifecycle

```mermaid
flowchart LR
    Enq["Enquiry<br/>website or front desk"] --> AppF["Application<br/>public form or staff"]
    AppF --> Docs["Documents and interview"]
    Docs --> Dec["Decision<br/>within seat limits"]
    Dec --> Enrol["Enrol as student"]
    Enrol --> Promo["Promotion or transfer<br/>each year"]
    Promo --> Cert["Certificates<br/>transfer, bonafide, character"]
    AppF -. "tracking link" .-> Family["Family checks status<br/>and uploads documents"]
```

- Families apply online at `/apply` and choose the class themselves. They get a reference number and a private tracking link. Staff can issue a fresh tracking link from the application.
- Seat limits and required documents are set per class. Follow-up and missing-document reminders are sent automatically.
- Certificates (transfer, bonafide, character, staff experience) are numbered in sequence and can be cancelled. ID cards carry a verification token.

### 3.3 Staff, leave, payroll and recruitment

```mermaid
flowchart LR
    Open["Job opening<br/>public careers page"] --> Appl["Applicant<br/>shortlisted, interview,<br/>offered, hired"]
    Appl --> Onb["Staff onboarding<br/>documents checklist"]
    Onb --> Leave["Leave request"] --> Appr["Approval<br/>balance updated"]
    Onb --> Sal["Salary structure"] --> Run["Payroll run<br/>draft, calculated,<br/>approved, paid"] --> Slip["Payslips"]
    Appr --> SAtt["Staff attendance"]
```

### 3.4 Timetable and attendance

```mermaid
flowchart LR
    Periods["Periods and rooms"] --> TT["Class timetable"]
    TT --> Sub["Substitutions"]
    TT --> Session["Attendance session"] --> Mark["Mark students"] --> Parents["Parents notified<br/>and portal updated"]
```

### 3.5 Examinations and results

```mermaid
flowchart TD
    Types["Exam types, grade boundaries,<br/>term weightage"] --> Exam["Examination"]
    QB["Question bank<br/>review and approval"] --> Paper["Paper builder<br/>blueprint rules"]
    Exam --> Sched["Exam schedule<br/>seating, invigilation duties"]
    Paper --> Sched
    Sched --> Marks["Marks entry<br/>change history kept"]
    Marks --> Results["Results and report cards<br/>co-scholastic grades"]
    Results --> Publish["Published to portals"]
    Publish --> Recheck["Recheck request<br/>optional fee, refund if marks change"]
    Results --> Supp["Supplementary exam<br/>for students who did not clear"]
    Sched --> Mal["Malpractice cases,<br/>room reports"]
```

- Browser-tested: marks entry, recheck with fee and refund, supplementary exam list and CSV export.

### 3.6 Fees and online payment

```mermaid
flowchart LR
    Heads["Fee heads and structures<br/>optional instalments"] --> Charge["Charge to class<br/>preview, safe to repeat"]
    Conc["Concessions and scholarships<br/>percentage or fixed"] --> Charge
    Charge --> Due["Student fees<br/>one per instalment, discounts"]
    Lib["Library fines"] --> Due
    Trans["Transport bills"] --> Due
    Due --> Desk["Collect at the desk<br/>receipt"]
    Due --> Online["Parent pays online<br/>Razorpay or eSewa order"]
    Online --> Verify["Signed callback or webhook<br/>verified once"]
    Verify --> Alloc["Payment allocated<br/>receipt"]
    Desk --> Alloc
    Alloc --> Rev["Reversal if needed<br/>with reason"]
    Due --> Follow["Dues follow-up calls<br/>promises to pay, reminders"]
```

- Online payments settle exactly once, even with duplicate callbacks, a late webhook or the parent's browser never returning. Pending orders are reconciled in the background.
- A structure can be split into instalments (for example 40/30/30 across three terms). Charging it to its class creates one student fee per instalment for every active student, with each student's concessions taken off; running it again only adds what is missing, such as students who joined later. The instalments are fixed once anyone has been charged.
- Library fines and transport bills each create a student fee, so they appear in the same dues and receipts.

### 3.7 Learning: course content, homework and assignments

```mermaid
flowchart TD
    Content["Course content by subject"] --> Enrol["Subject enrolment"]
    HW["Homework with attachments"] --> Prog["Student progress<br/>reminders"]
    Assign["Assignments"] --> Submit["Submissions"] --> Grade["Grading"]
```

### 3.8 Communication

```mermaid
flowchart TD
    Ann["Announcement<br/>now or scheduled"] --> Rec["Recipients by role, class"]
    Rec --> Notif["In-app notification<br/>and web push"]
    Rec --> Out["Email and WhatsApp outbox<br/>retried if delivery fails"]
    PTM["Parent-teacher meetings<br/>sessions and slots"] --> Book["Parents book a slot"]
    Cal["School calendar events"]
```

### 3.9 Operations

- **Front office:** visitor log with badges, student gate passes with a picked-up-by record, postal in and out.
- **Library:** catalogue, copies, loans and returns, fines.
- **Transport:** vehicles, drivers, routes and stops, student assignment, transport bills.
- **Inventory:** stock items and locations, suppliers and purchases, assets with assignment and maintenance.
- **Expenses:** categories, payment accounts, cashbook.
- **Data import:** CSV import of students, staff and opening balances.
- **Health records:** each student's allergies, conditions, medicines and doctor, an incident log that cannot be deleted, and a per-section list of students to know about. Teachers read, a nurse or the office edits, and a parent reads their own child's.
- **Audit logs:** who changed what.
- **System Health:** API traffic, errors and background-job heartbeat. The full view is for platform operators. School owners see their own school.

## 4. Not built yet

These gaps were found in the code. They are candidates, not commitments.

- **Hostel:** no rooms, allocation or hostel fees.
- **Learning extensions:** no quizzes inside course content and no lesson ordering or progress tracking beyond homework progress.

## 5. Notes

- Academic years exist. Some models link to a year, and the rest of the year migration is still a planned piece of work.
- Every school API refuses a malformed query value with a 400 response, not a server error.
- This document describes the design. Infrastructure and deployment are covered under `deploy/`.
