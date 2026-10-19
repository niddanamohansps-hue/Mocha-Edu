# EDU Sekai — System Architecture and Module Workflows

> **Scope:** Documentation only. Diagrams distinguish current code from proposed, unimplemented workflows. Based on repository inspection; this is not a runtime verification.

## 1. System architecture

```mermaid
flowchart TB
    subgraph Clients["Web clients"]
        Public["Public SaaS site<br/>Next.js :3000<br/>School signup and billing"]
        TenantUI["Tenant dashboard<br/>Next.js :3555<br/>School-specific subdomain"]
    end
    subgraph Backend["Django REST API"]
        TenantRouting["Tenant middleware<br/>request host → tenant schema"]
        Auth["Accounts / authentication<br/>JWT cookie"]
        RBAC["Tenant roles and permissions"]
        PublicAPI["Public APIs<br/>auth · organizations · signup payments"]
        TenantAPI["Tenant APIs<br/>students · staff · families · academics<br/>attendance · timetable · exams · fees<br/>LMS · parent portal · notifications<br/>announcements · dashboard · audit"]
        Celery["Celery workers and Beat<br/>email outbox · scheduled announcements"]
    end
    subgraph Database["PostgreSQL — django-tenants"]
        PublicSchema["Public schema<br/>users · organizations/domains · signup payment records"]
        TenantSchemas["One schema per school<br/>profiles · roles · students · staff · families<br/>academics · attendance · timetable · exams · fees<br/>course content · parent portal · notifications<br/>announcements · audit"]
    end
    Redis["Redis<br/>Celery broker"]
    SMTP["Email / SMTP"]
    Esewa["eSewa<br/>school signup only"]

    Public --> PublicAPI
    TenantUI --> TenantRouting
    TenantRouting --> Auth
    TenantRouting --> RBAC
    TenantRouting --> TenantAPI
    TenantRouting --> PublicAPI
    PublicAPI --> PublicSchema
    Auth --> PublicSchema
    RBAC --> TenantSchemas
    TenantAPI --> TenantSchemas
    PublicAPI -->|"successful signup provisions tenant"| TenantSchemas
    Public -->|"signup payment"| Esewa
    Esewa -->|"callback verification"| PublicAPI
    TenantAPI -->|"outbox task after commit"| Redis
    Celery --> Redis
    Celery --> TenantSchemas
    Celery --> SMTP
```

**Tenant isolation:** The school subdomain/domain selects the PostgreSQL schema. Operational school records are tenant-local. Global accounts are in the public schema and are referenced from tenant profiles with UUID soft links, not cross-schema foreign keys.

## 2. Current core school workflow

```mermaid
flowchart LR
    Setup["School / tenant setup"] --> Academic["Program → level → section → subject"]
    Setup --> Staff["Profile → staff member → instructor"]
    Setup --> Family["Parent / guardian records"]
    Academic --> Enroll["Student enrollment<br/>StudentLevel + year"]
    Family --> Enroll
    Enroll --> Timetable["Timetable<br/>periods, rooms, weekly entries"]
    Enroll --> Attendance["Attendance sessions and marks"]
    Enroll --> LMS["Course content and assignments"]
    Enroll --> Exams["Exam schedules and marks"]
    Exams --> Results["Calculate and publish results"]
    Enroll --> Fees["Fee structure → student fee"]
    Fees --> Payment["Record payment → allocation → receipt"]
    Results --> ParentPortal["Parent portal<br/>results, attendance, fees, timetable"]
    Attendance --> ParentPortal
    Payment --> ParentPortal
    Timetable --> ParentPortal
    Staff --> Teaching["Teaching assignments / grading"]
    Teaching --> LMS
    Teaching --> Exams
```

## 3. Current module workflows

### 3.1 Tenant provisioning, login and access control

```mermaid
sequenceDiagram
    actor Owner as School owner
    participant Site as Public Next.js site
    participant API as Django API
    participant Gateway as eSewa
    participant PublicDB as Public schema
    participant TenantDB as Tenant schema
    Owner->>Site: Submit school and owner details
    Site->>API: Initialize signup payment
    API->>PublicDB: Store pending signup payment
    API-->>Site: Payment details and signature
    Site->>Gateway: Complete payment
    Gateway->>API: Callback
    API->>API: Verify signature and amount
    API->>PublicDB: Mark payment complete; create organization/domain/user
    API->>TenantDB: Create tenant schema and migrate
    Owner->>API: Log in on school domain
    API->>TenantDB: Resolve local profile and tenant role
    API->>PublicDB: Authenticate global account
    API-->>Owner: JWT cookies
```

```mermaid
flowchart LR
    Request["Request to tenant domain"] --> Resolve["Resolve domain → Organization"]
    Resolve --> Context["Activate tenant schema"]
    Context --> JWT["Authenticate global account"]
    JWT --> Profile["Resolve tenant-local profile"]
    Profile --> Role["Load active tenant role(s)"]
    Role --> Check{"Required permission?"}
    Check -->|yes| Endpoint["Run tenant-scoped API"]
    Check -->|no| Forbidden["403 Forbidden"]
```

### 3.2 Student, academic and family lifecycle

```mermaid
flowchart TD
    A["Create program, levels, sections, subjects"] --> B["Admin enrollment workflow"]
    P["Create parent / guardian"] --> R["Link parent to student"]
    B --> S["Create student and profile"]
    S --> R
    A --> E["Assign level, section and academic year"]
    S --> E
    T["Staff and instructor onboarding"] --> SA["Assign instructor to subject/section"]
    A --> SA
    E --> Promo["Promotion preview and execution"]
    Promo --> Hist["Append promotion history"]
    Promo --> Next["New enrollment / lifecycle transition"]
    Next -.-> Transfer["Transfer/withdrawal status exists;<br/>full workflow remains incomplete"]
```

The dashboard's admissions route is an admin-side enrollment wizard, not a prospective-applicant application pipeline.

### 3.3 Timetable and attendance

```mermaid
flowchart LR
    Year["Academic year"] --> Period["Configure periods"]
    Room["Optional rooms"] --> Entry["Create weekly timetable entry"]
    Period --> Entry
    Section["Section + subject"] --> Entry
    Instructor["Instructor"] --> Entry
    Entry --> Views["Class and instructor schedules"]
    Entry --> Sub["Date-specific substitution"]

    Section --> Session["Create daily attendance session"]
    Session --> Marks["Bulk mark students<br/>present / absent / late / half-day / leave"]
    Marks --> Lock["Edit or lock session"]
    Marks --> Report["Attendance summaries and reports"]
    Staff["Staff"] --> StaffAttendance["Record staff attendance"]
```

### 3.4 Examinations and results

```mermaid
flowchart TD
    Type["Configure exam type"] --> Exam["Create examination"]
    Year["Academic year"] --> Exam
    Exam --> Schedule["Create subject/section schedules"]
    Schedule --> Marks["Enter marks / absence"]
    Boundaries["Configure grade boundaries"] --> Calc["Calculate results"]
    Marks --> Calc
    Calc --> Publish["Publish examination"]
    Publish --> Snapshot["Immutable ExamResult snapshots"]
    Snapshot --> StudentView["Student results"]
    Snapshot --> ParentView["Parent results and report-card data"]
```

### 3.5 Fees and payment recording

```mermaid
flowchart LR
    Head["Create fee head"] --> Structure["Define fee by level/section/year"]
    Structure --> Assign["Assign fee to student"]
    Student["Student"] --> Assign
    Assign --> Due["StudentFee: amount, discount, due date"]
    Due --> Receive["Record payment"]
    Receive --> Allocation["Allocate against student fees"]
    Allocation --> Receipt["Receipt view / number"]
    Allocation --> Balance["Outstanding balance and report"]
    Balance --> Parent["Parent fee view"]
    Receive --> Reverse["Reverse via offsetting payment"]
    Reverse --> Allocation
```

This is manual payment recording. The eSewa signup flow does not currently mean that students or parents can pay school fees online.

### 3.6 Course content and assignments

```mermaid
flowchart TD
    Teacher["Staff / instructor"] --> Content["Create notes, documents, videos, links"]
    Content --> Target["Target programs, levels, sections,<br/>subjects or specific students"]
    Target --> StudentView["Student views eligible published content"]
    Teacher --> Assignment["Create assignment<br/>due date, points, submission rules"]
    Assignment --> Submission["Student submits file, text or link"]
    Submission --> Grade["Teacher grades and adds feedback"]
    Grade --> Feedback["Student views score and feedback"]
```

### 3.7 Announcements and notifications

```mermaid
flowchart TD
    Author["Authorized staff"] --> Draft["Create announcement draft"]
    Draft --> Audience["Choose audience<br/>all / staff / parents / students / section / level"]
    Audience --> Publish["Publish now or schedule"]
    Publish --> Resolve["Resolve eligible recipients in tenant"]
    Resolve --> Snapshot["Persist recipient snapshot"]
    Resolve --> Inbox["Create in-app notifications"]
    Resolve --> Outbox["Create email outbox event(s), if selected"]
    Outbox --> Worker["Celery worker sends email"]
    Beat["Celery Beat, every 5 min"] --> Due["Publish due announcements"]
    Beat --> Retry["Recover stale outbox events, every 10 min"]
    Snapshot --> Mine["Recipient views their announcements"]
```

## 4. Proposed workflows — not implemented modules

Dashed arrows and headings in this section are proposals based on identified gaps; they do not describe existing application behavior.

### 4.1 Admissions applicant pipeline

```mermaid
flowchart LR
    Enquiry["Prospective family enquiry"] --> Application["Applicant application"]
    Application --> Docs["Collect required documents"]
    Docs --> Review["Review / verify application"]
    Review --> Decision{"Decision"}
    Decision -->|"More information"| Application
    Decision -->|"Reject"| Rejected["Reject / archive"]
    Decision -->|"Accept"| Offer["Offer / acceptance"]
    Offer --> Convert["Convert applicant to student"]
    Convert --> Student["Create student profile"]
    Student --> Enroll["Assign level, section, academic year"]
```

### 4.2 Staff leave and attendance reconciliation

```mermaid
flowchart LR
    Staff["Staff member"] --> Request["Submit leave request"]
    Request --> Approver["Approver reviews"]
    Approver --> Decision{"Approve?"}
    Decision -->|no| Declined["Decline and notify"]
    Decision -->|yes| Balance["Update leave balance"]
    Balance --> Calendar["Record approved dates"]
    Calendar --> Attendance["Reconcile attendance"]
```

### 4.3 Fee online payment, installments and scholarships

```mermaid
flowchart LR
    StudentFee["Student fee / installment"] --> Initiate["Initiate online payment"]
    Initiate --> Gateway["Payment provider"]
    Gateway --> Verify["Verify signed callback"]
    Verify --> Allocate["Allocate payment to outstanding fee"]
    Allocate --> Receipt["Issue receipt and update balance"]
    Scholarship["Approve scholarship / concession"] --> StudentFee
    Installments["Configure installment plan"] --> StudentFee
    Allocate --> ParentPortal["Update parent fee view"]
```

### 4.4 Student transfer, documents and certificates

```mermaid
flowchart LR
    Student["Student transfer / withdrawal request"] --> Review["Review and approve transition"]
    Review --> Clearance["Fee / library / asset clearances"]
    Clearance --> Status["Record transfer or withdrawal"]
    Status --> Certificate["Generate certificate from template"]
    Certificate --> Number["Assign certificate number"]
    Number --> Verify["Optional public verification"]
    Status --> History["Retain lifecycle history"]
```

### 4.5 Library and transport

```mermaid
flowchart TD
    Catalogue["Book catalogue and copies"] --> Issue["Issue to student/staff"]
    Issue --> Due["Track due date and renewal"]
    Due --> Return["Return book"]
    Due --> Fine["Assess overdue fine"]
    Fine -.-> Fees["Link fine to fees — proposed"]

    Route["Define routes, stops and vehicles"] --> Assignment["Assign student to route"]
    Assignment --> TransportFee["Apply route-linked transport fee"]
    Driver["Maintain driver records/documents"] --> Route
```

### 4.6 Health, calendar, LMS extensions and inventory

```mermaid
flowchart TD
    Student["Student"] --> Medical["Restricted medical profile"]
    Medical --> Allergies["Allergies / conditions"]
    Medical --> Incident["Medical incident / treatment"]
    Medical --> Emergency["Emergency contacts"]

    Year["Academic year"] --> Calendar["School calendar"]
    Calendar --> Events["Holidays, events, deadlines"]
    Events --> Timetable["Inform timetable and school operations"]
    Events --> Notice["Publish related notice"]

    Teacher["Teacher"] --> Lessons["Ordered lessons / units"]
    Lessons --> Quiz["Quiz / assessment"]
    Quiz --> Progress["Track learner progress"]
    Progress --> Report["Teacher progress reporting"]

    Supplier["Supplier"] --> Order["Purchase request/order"]
    Order --> Receive["Receive stock"]
    Receive --> Stock["Stock ledger"]
    Stock --> Issue["Issue consumables"]
    Asset["Register durable asset"] --> Assign["Assign to staff/room"]
    Assign --> Maintain["Maintenance history"]
    Maintain --> Retire["Dispose / retire asset"]
```

## 5. Suggested dependency roadmap

```mermaid
flowchart LR
    Foundation["Tenant setup, identity, RBAC"] --> AcademicYear["Complete academic-year migration / workflow"]
    AcademicYear --> Admissions["Applicant admissions"]
    Admissions --> Students["Student lifecycle and enrollment"]
    Students --> Core["Attendance · timetable · exams · fees · LMS"]
    Core --> Portal["Parent portal and communication"]
    Students --> Documents["Documents, transfers, certificates"]
    Staff["Staff onboarding"] --> Leave["Leave management"]
    Leave --> Attendance["Attendance reconciliation"]
    Core --> OnlineFees["Student/parent online payments"]
    Core --> FeePlans["Installments and scholarships"]
    Students --> Library["Library"]
    Students --> Transport["Transport"]
    Core --> Reports["Reporting and analytics"]
    Staff --> HR["HR depth"]
    HR -.-> Payroll["Payroll — future / optional"]
```

## 6. Current implementation caveats

- Announcements are implemented in the backend and tenant frontend; earlier gap-analysis entries calling them missing are stale.
- The parent portal reads child attendance, timetable, published results, and fees, with child-access checks.
- Student fee online payment is separate from the public school signup payment integration.
- The AcademicYear entity exists and nullable FK fields have been added in some models, but planning documents state that the larger FK backfill/dual-write phase remains unapproved and has unresolved decisions. Do not infer that year migration is complete from the presence of the model or fields.
- This diagram is a documentation summary. It does not establish that deployment infrastructure, external services, or every UI/API path has been runtime-tested.
