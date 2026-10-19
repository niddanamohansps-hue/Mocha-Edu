# EDU Sekai Backend

The backend for EDU Sekai is a multi-tenant Django REST API that provides complete data isolation for educational institutions while maintaining a shared authentication system.

---

## Architecture Overview

### Multi-Tenant Design Philosophy

The backend implements **schema-based multi-tenancy** using PostgreSQL's native schema feature combined with Django Tenants. This provides the strongest form of data isolation available in relational databases.

**Two Schema Categories:**

1. **Public Schema (Shared)**
   Contains global data that applies across the entire SaaS platform:
   - User authentication credentials (username, password hash)
   - Organization registry (school metadata, subdomain mappings)
   - Payment and billing records
   - System-wide configuration

2. **Tenant Schemas (Isolated)**
   Each school receives its own dedicated schema (e.g., `school_oxford`, `school_cambridge`) containing:
   - Student academic records and enrollment data
   - Staff employment information
   - Roles, permissions, and access control rules
   - Guardian (parent) profiles and relationships
   - Institution-specific settings and preferences

**How Isolation Works:**
- Physical separation at the database level
- Queries cannot accidentally access other schools' data
- Each request sets PostgreSQL's `search_path` to the appropriate schema
- No filtering logic required - wrong data literally doesn't exist in the search path

---

## The Soft-Link Identity System

### Why Not Foreign Keys?

Traditional Django projects use database Foreign Keys to link related tables. However, in a multi-schema environment:

**The Problem:**
- PostgreSQL Foreign Keys require both tables to exist in the same schema
- A tenant table (e.g., `school_oxford.profiles_profile`) cannot have a Foreign Key to a public table (e.g., `public.accounts_user`)
- Attempting to create cross-schema Foreign Keys causes migration failures
- Django's admin interface tries to follow Foreign Key relationships and crashes when they span schemas

**The EDU Sekai Solution:**
Instead of database-enforced Foreign Keys, we use **UUID-based soft links**:
- Profiles store the User's ID as a plain UUID field (`user_id`)
- The relationship exists at the application layer, not the database layer
- Django signals handle cascading operations (e.g., when a User is deleted)

**Benefits:**
1. **Admin Stability:** Django's admin panel works without attempting impossible cross-schema joins
2. **Horizontal Scalability:** Tenant schemas can be migrated to different database servers
3. **Performance:** No Foreign Key constraint checking overhead across schemas
4. **Flexibility:** Users can be "soft-deleted" without triggering cascading deletes across all tenant schemas

**Trade-Off:**
Referential integrity must be maintained through application logic rather than database constraints. This is why we provide audit scripts to detect and fix broken links.

---

## Authentication & Username Resolution

### Dual-Username Strategy

The system balances user-friendliness with technical requirements through a two-tier username structure:

**Local Usernames (School Context)**
- Format: `firstnamemiddlenamelastname` (e.g., `alicejoneswilliams`)
- Uniqueness: Only within a specific school's schema
- Purpose: What users actually type during login
- Storage: Tenant schema's Profile table
- Collision handling: If duplicate, append counter (e.g., `alicejoneswilliams2`)

**Global Usernames (System Context)**
- Format: `localusername_randomhex` (e.g., `alicejoneswilliams_7f3a19`)
- Uniqueness: Globally unique across the entire SaaS platform
- Purpose: Django's authentication backend requirement
- Storage: Public schema's User table
- Visibility: Hidden from end users

### Login Resolution Process

When a user attempts to log in:

1. **Input:** User types `alicejoneswilliams` at `oxford.localhost:3555`
2. **Context Detection:** Middleware identifies the tenant as `school_oxford`
3. **Profile Lookup:** System queries `school_oxford.profiles_profile WHERE local_username = 'alicejoneswilliams'`
4. **User ID Retrieval:** Profile returns its `user_id` (the soft link UUID)
5. **User Fetch:** System queries `public.accounts_user WHERE id = <user_id>`
6. **Global Username:** Retrieved User object contains `username = 'alicejoneswilliams_7f3a19'`
7. **Authentication:** Django's authentication backend verifies password against this User
8. **Success:** User is authenticated in Oxford's tenant context

**Why This Works:**
- Users experience simple, intuitive usernames
- Each school maintains its own username namespace (no global collision worries)
- The platform ensures true global uniqueness behind the scenes
- Same person can use different local usernames in different schools (e.g., teacher in School A, parent in School B)

---

## Role-Based Access Control (RBAC)

### Tenant-Scoped Permission System

As of January 2026, the RBAC system operates entirely within tenant schemas. Each school has its own isolated set of roles and permissions.

**Core Components:**

1. **Permissions**
   - Atomic actions: `view_student`, `add_staff`, `delete_parent`, etc.
   - Module-grouped for UI organization (Students, Staff, Roles, etc.)
   - Defined in `roles/constants.py` and seeded automatically

2. **Roles**
   - Collections of permissions: Owner, Admin, Teacher, Student, etc.
   - System roles: Pre-configured, cannot be deleted, can be customized
   - Custom roles: School-specific (e.g., Librarian, Counselor, Bus Coordinator)

3. **UserRole Assignments**
   - Links global Users to tenant-specific Roles
   - One user can have multiple roles in the same school
   - Same user can have different roles in different schools

**How Permission Checking Works:**

When a request hits a protected endpoint:
1. Authentication confirms the User's identity
2. Middleware sets the tenant context based on subdomain
3. Permission decorator checks if the User has a role assignment in THIS tenant
4. System queries the tenant's UserRole table for active assignments
5. Checks if any assigned role includes the required permission
6. Grants or denies access accordingly

**Isolation Guarantees:**
- Oxford's "Teacher" role is completely independent of Cambridge's "Teacher" role
- Permissions can be customized per school without affecting others
- Custom roles in one school don't appear in other schools' lists
- UserRole table exists in each tenant schema, not globally shared

---

## Portal Activation Workflow

Students and staff don't automatically get login credentials when they're admitted or hired. Portal activation is a deliberate, controlled process.

**Phase 1: Profile Creation (Identity)**
- Admin admits a new student/staff member through the dashboard
- Profile is created in the tenant schema with personal information
- No User account exists yet (`profile.user_id = NULL`)
- Person exists in the school system but cannot log in

**Phase 2: Account Activation (Access)**
- Admin initiates portal activation for selected profiles
- System generates local username from profile name
- Creates corresponding User account in public schema
- Links Profile to User via `user_id` soft link
- Assigns appropriate role (Student, Instructor, etc.)
- Generates temporary password with forced-change flag

**Phase 3: First Login (Personalization)**
- User enters their local username and temporary password
- System resolves to global User account
- Mandatory password change modal appears
- User sets permanent password
- Dashboard access granted

**Security Features:**
- Passwords are never stored in plain text (Django's PBKDF2 hashing)
- Initial passwords are one-time use only
- Password complexity requirements enforced
- Account activation can be revoked by removing the User link

---

## Data Isolation & Tenant Routing

### Request-Level Schema Switching

Every incoming HTTP request goes through tenant detection:

1. **Domain Extraction:** Middleware reads the `Host` header
2. **Tenant Lookup:** Queries `organizations_domain` table to find matching Organization
3. **Schema Activation:** Sets PostgreSQL connection's `search_path` to the tenant's schema
4. **Query Execution:** All ORM queries now operate within that schema only
5. **Response:** Data from that schema alone is returned

**Example Flow:**
```
GET http://oxford.localhost:8000/api/students/

→ Middleware extracts: hostname = "oxford.localhost"
→ Lookup: Domain.objects.get(domain="oxford.localhost")
  Returns: Organization(schema_name="school_oxford")
→ Execute: SET search_path TO school_oxford
→ Query: Student.objects.all()
  Reads from: school_oxford.students_student table
→ Response: Only Oxford's students
```

**Impossibility of Cross-Tenant Access:**
Even if application code attempted to query another tenant's data, PostgreSQL wouldn't find the table because it's not in the current `search_path`. The isolation is database-enforced, not just application logic.

---

## Development & Maintenance Tools

### Automated Seeding

**Public Tenant Setup:**
The `seed_public.py` script is **not** run automatically at container start any more. Run it once by hand after the shared migrations have been applied (`docker compose exec backend python seed_public.py`, or `python seed_public.py` from `backend/`). It ensures:
- Public tenant exists with `localhost` domain mapping
- Superuser account is created from environment variables
- Infrastructure is ready for the first school registration

`seed_public.py` has no database-identity check yet, so confirm which database the environment points at before running it.

**Tenant Role Initialization:**
Django signals detect when a new tenant schema is migrated and automatically seed:
- System permissions (all available actions in the system)
- System roles (Owner, Admin, Teacher, Student)
- Role-permission assignments (Owner gets all permissions)

This ensures every school starts with a functional RBAC system without manual setup.

### Migration safety

`python manage.py migrate` and `python manage.py migrate_schemas` are the **same command** in this project (`django-tenants` replaces `migrate`). With no options they migrate the shared schema and **every tenant**. For that reason `manage.py` refuses to apply migrations unless the scope and the target database are stated explicitly.

**Requirements for an apply**
- Exactly one scope: `--shared`, `--tenant`, or `--schema NAME` (`--schema public` is the shared schema). Combinations such as `--shared --tenant` or `--schema acme --tenant`, and repeated scope options, are refused: run the shared and tenant steps as separate commands.
- `--apply`.
- `--confirm-database NAME`, equal to the configured database name (`DB_NAME`).
- `EDUSEKAI_EXPECTED_DATABASE=name@host:port` set for the process (in `.env` or in the shell) and equal to the configured `DB_NAME`, `DB_HOST` and `DB_PORT` **exactly**. `127.0.0.1` and `localhost` are different identities, and there is no exception for `test_` databases. An unset or malformed value refuses the apply.

**Commands** (development database `edusekai_db`; run from `backend/`)
```bash
# Inspect (no --apply or confirmation, but exactly one scope and a matching EDUSEKAI_EXPECTED_DATABASE; see the caveat below)
python manage.py migrate_schemas --shared --plan
python manage.py showmigrations

# Apply
python manage.py migrate_schemas --shared --apply --confirm-database edusekai_db
python manage.py migrate_schemas --tenant --apply --confirm-database edusekai_db
python manage.py migrate_schemas --schema <tenant> --apply --confirm-database edusekai_db
python manage.py migrate_schemas --schema <tenant> <app> --apply --confirm-database edusekai_db   # one app, forward only
```
Staging and production identities are not documented here: each environment sets its own `EDUSEKAI_ENV` and `EDUSEKAI_EXPECTED_DATABASE`, and the release procedure is defined by the project owner.

**Protected operations** also need `--allow-destructive`: an explicit migration name (for example `certificates 0001`, or `zero`), `--fake`, `--fake-initial`, `--prune` and `--run-syncdb`. `--prune --plan` counts as protected (Django prunes before it plans). `--allow-destructive` is refused when none of these is present.

**Refused**
- A bare `migrate` / `migrate_schemas`, or an apply without a scope, `--apply` or the confirmation.
- `--list` and `-l`: `django-tenants` accepts them but nothing reads them, so the command would carry on and apply migrations. Use `python manage.py showmigrations` instead. To look at one tenant, `tenant_command showmigrations --schema=<tenant>` does not migrate anything (this form has not been exercised in this project yet).
- `tenant_command` / `all_tenants_command` lines that contain, as a separate token at any position, `migrate`, `migrate_schemas`, `tenant_command` or `all_tenants_command`. Migrations cannot be routed through the wrappers, and wrappers cannot be nested (a wrapper inside a wrapper would reach `migrate_schemas` without passing the gate). The check is by token, not by position, so `--no-public`, `--schema` and the nesting depth do not matter. **Known limitation:** a separate token equal to one of those names is refused even when it is only an argument value, for example `tenant_command shell -s migrate` for a tenant schema named `migrate` (the inline form `--schema=migrate` is a single token and is not affected). Other wrapped commands, such as `tenant_command showmigrations --schema=<tenant>`, are not affected.
- `--settings` / `--pythonpath` and a `--database` other than `default` when applying or running `--plan` / `--check`, so the identity check cannot be pointed at a different configuration.
- A first argument that starts with `-`, other than the exact forms `manage.py --help`, `manage.py -h` and `manage.py --version` (for example `manage.py --settings=x migrate_schemas ...`). `--help` and `--version` after a command name are still accepted: they exit without migrating.
- `--plan` / `--check` without exactly one scope, without `EDUSEKAI_EXPECTED_DATABASE`, or against a database that does not match it.
- More than one scope, or a repeated scope option (an apply names exactly one scope).
- Unknown options and abbreviated options (Django accepts abbreviations, which could hide a protected option).

**Messages.** Refusals never echo what you typed. An unrecognized or abbreviated token is reported only by its position (`token #N`, where `manage.py` is `#0`); option values, schema names, confirmation values and positional arguments are never printed, so a secret typed by mistake is not repeated on screen or in logs.

**The notice.** When a command passes the gate, stderr shows `Migration gate: checks passed for database ...`. It is printed only after every gate check has passed, and it only means that the gate's own checks passed and the command is being handed to Django. It does not mean Django accepted the arguments or that any migration was applied.

**`--plan` and `--check` are not guaranteed to be read-only, so they are checked like an apply.** They need exactly one scope and the same target checks (a valid `EDUSEKAI_EXPECTED_DATABASE` that matches exactly, no `--settings` / `--pythonpath`, only the `default` database). They do not need `--apply` or `--confirm-database`, and those two are refused when given with them. When the checks pass, stderr says `Migration gate: checks passed for the configured database ...` and that the operation is not guaranteed to be read-only and that the notice does not mean Django accepted the arguments. A protected operation combined with them (for example `--prune --plan`) is an apply and needs all the apply flags. For every schema, `django-tenants` calls `MigrationRecorder.ensure_schema()` before running the command, which creates the `django_migrations` table if that schema does not have one. `--check` also stops at the first schema with pending migrations.

**Disposable database rehearsals.** Set **both** `DB_NAME` and `EDUSEKAI_EXPECTED_DATABASE` for that single process. An apply then uses the normal apply flags; a plan-only run (shown after it) uses neither `--apply` nor `--confirm-database`. There is no bypass flag, and setting both wrongly defeats the check:
```bash
DB_NAME=my_disposable_db EDUSEKAI_EXPECTED_DATABASE=my_disposable_db@127.0.0.1:5432 \
  python manage.py migrate_schemas --shared --apply --confirm-database my_disposable_db
# plan only (same variables; no --apply or --confirm-database):
DB_NAME=my_disposable_db EDUSEKAI_EXPECTED_DATABASE=my_disposable_db@127.0.0.1:5432 \
  python manage.py migrate_schemas --shared --plan
```

**Docker**
- Migrations at container start are off by default. Only `RUN_MIGRATIONS_ON_START=true` (exactly) runs them; `makemigrations` is never run at start. Generate migrations while developing and commit them.
- When enabled, the entrypoint applies the shared migrations and then the tenant migrations as two separate gated steps, and `EDUSEKAI_EXPECTED_DATABASE` must be in the container environment. If a step fails the server does not start, and migrations that were already applied are not reversed automatically.
- A deliberate one-off run is preferred over migrating on every start, for example `docker compose run --rm backend python manage.py migrate_schemas --shared --apply --confirm-database <DB_NAME>` and then the `--tenant` form (this has not been exercised in this project yet).
- `docker compose run` (like `docker compose up`) executes the image entrypoint before your command. If `RUN_MIGRATIONS_ON_START=true` is set in `.env` or your shell, a one-off `docker compose run --rm backend ...` therefore applies the shared and tenant migrations through the entrypoint first, and only then runs your command (this has not been exercised in this project).
- In Docker the confirmation is supplied by the entrypoint: it passes `--confirm-database "$DB_NAME"` from the container's own `DB_NAME`, so there is no human typing step. The protections on that path are the exact `true` opt-in switch, the required `EDUSEKAI_EXPECTED_DATABASE` identity check, the single explicit scope per step, and failing fast.
- Safer one-off workflow: keep `RUN_MIGRATIONS_ON_START` unset or `false` (or pass `-e RUN_MIGRATIONS_ON_START=false` to `docker compose run`; untested here), inspect with `docker compose run --rm backend python manage.py migrate_schemas --shared --plan` (this needs `EDUSEKAI_EXPECTED_DATABASE` in the container environment, equal to the intended `name@host:port`; otherwise the gate refuses it), then apply with flags you type yourself: `docker compose run --rm backend python manage.py migrate_schemas --shared --apply --confirm-database <DB_NAME>` and then the `--tenant` form.
- `docker-compose.yml` sets `restart: on-failure:3` for the backend. The cap applies to **any** backend failure, not only migration failures: after 3 consecutive failed restarts the container stays stopped until it is started again. If a start-time migration fails, stop the service, fix the cause and unset `RUN_MIGRATIONS_ON_START` instead of letting it retry.
- `entrypoint.sh` is copied into the image at build time, so rebuild the image after changing it. An old image still runs its old entrypoint.
- Seed the public tenant by hand (see Automated Seeding above).

**What the gate does not protect.** It only inspects `python manage.py ...` on the command line. It does not see `call_command(...)` (used by Django's test runner and by tenant provisioning), `django-admin`, `python -m django`, `manage.py shell` sessions, or other scripts, which can still migrate. It guards against accidents; it is not a security boundary. The identity check compares configuration values (the settings module), not the connection that is actually opened: libpq environment variables, service files, an `OPTIONS` entry, a proxy or DNS can still lead to another server. Hardening for the environment and `OPTIONS` is deferred.

**Commands outside the gate.** The gate looks only at `migrate` / `migrate_schemas` (and refuses them when routed through `tenant_command` / `all_tenants_command`). It is not a universal database-change guard. These are **not** guarded:
- `django-tenants` schema management: `create_tenant`, `clone_tenant`, `delete_tenant`, `rename_schema`, `create_missing_schemas`, `create_domain`, `delete_domain`, `create_tenant_superuser`, `collectstatic_schemas`, and `tenant_command` / `all_tenants_command` running any command other than a migration.
- Tenant creation through other routes: the `register_organization` API signup and the `seed_demo_school` / `seed_realistic_school` commands create an `Organization`, which creates and migrates that tenant's schema through `call_command`, which the gate cannot see.
- Project commands and scripts that write data or schema objects: `populate_test_data`, `backfill_academic_years`, `seed_public.py`, and `cleanup_public_db.py` (which can drop tables when run as a script).
- Django commands that change the database by other routes, for example `flush`, `loaddata`, `dbshell`, `shell` and `createsuperuser`; `makemigrations` writes migration files only.
Guards for the tenant-administration commands are a separate, later decision.

### Integrity Audit Scripts

Because soft links don't have database-level integrity constraints, we provide maintenance commands:

**Orphan Detection:**
```bash
python manage.py audit_orphans
```
Scans all tenant schemas for profiles with `user_id` values that point to non-existent User accounts. This can happen if:
- A User is deleted directly from the admin panel
- Data is manually manipulated in the database
- Sync issues occur during development resets

**Orphan Cleanup:**
```bash
python manage.py audit_orphans --fix
```
Sets `user_id = NULL` for all broken references, effectively "deactivating" those accounts.

**Unlinked Profile Inventory:**
```bash
python manage.py audit_unlinked
```
Lists profiles that don't have associated User accounts (students/staff who haven't been given portal access yet).

These tools maintain the application-level referential integrity that the soft-link pattern requires.

### Test Data Generation

**Populate Mock Data:**
```bash
python manage.py populate_test_data --schema=<schema_name>
```
Uses the `Faker` library to generate realistic test data for a specific tenant.
- Populates PROGRAMS, SECTIONS, SUBJECTS, STAFF, STUDENTS, and FAMILIES.
- Generating COURSE CONTENT (assignments, submissions) with varied statuses.
- Ensures referential integrity and avoids duplicates.
- **Example:** `python manage.py populate_test_data --schema=school_oxford`

> **Note:** User passwords are set to `password123` by default for generated accounts.

### Testing Infrastructure

**Test Coverage:**
- Multi-tenant isolation verification (queries don't leak across schemas)
- Authentication flow (username resolution, soft-link traversal)
- Permission enforcement (RBAC system correctness)
- Data integrity (profile-user relationships remain valid)

**Running Tests:**
```bash
# All tests
docker compose exec backend python manage.py test

# Specific modules
docker compose exec backend python manage.py test accounts
docker compose exec backend python manage.py test students
docker compose exec backend python manage.py test roles
```

---

## Performance Optimizations

### N+1 Query Elimination

Cross-schema User lookups are a potential bottleneck. When displaying a list of 50 students with their email addresses, naive implementation would cause 51 database queries (1 for students + 50 for individual Users).

**Optimization Strategy:**
- Fetch all profiles in a single query
- Extract `user_id` values from the result set
- Bulk fetch Users from public schema in one query
- Build an in-memory map (dictionary) for instant lookup
- Attach Users to profile instances via `_user_cache` attribute
- Serializer accesses cached Users instead of hitting the database

**Performance Gain:** 95% reduction in database queries for list views.

### Strategic Indexing

Database indexes are applied to commonly queried fields:
- Profile: Composite index on (`user_id`, `local_username`) for login resolution
- Student: Index on (`status`, `admission_date`) for filtering active students
- UserRole: Index on (`user`, `role`, `is_active`) for permission checks

### Transaction Safety

All multi-step operations (enrollment, activation, role assignment) are wrapped in atomic transactions. If any step fails, all changes are rolled back, preventing partial data corruption.

---

## API Endpoints

**Authentication (Public):**
- `POST /api/auth/login/` - User authentication
- `POST /api/auth/logout/` - Session termination
- `POST /api/auth/refresh/` - JWT token refresh
- `GET /api/auth/me/` - Current user info + roles in current tenant
- `POST /api/auth/change-password/` - Password update

**Organization Management (Public):**
- `POST /api/organizations/register/` - New school registration
- `GET /api/organizations/check-domain/` - Subdomain availability

**Payment Processing (Public):**
- `POST /api/payments/init/` - Initialize eSewa payment
- `GET /api/payments/verify/` - Verify payment callback

**Student Management (Tenant):**
- `GET /api/students/` - List students
- `POST /api/students/enroll/` - Admit new student
- `POST /api/students/portal-activation/` - Create student accounts
- `GET /api/students/credential-distribution/` - List unclaimed credentials
- `GET/PUT/DELETE /api/students/{id}/` - Student detail operations

**Staff Management (Tenant):**
- `GET /api/staff/` - List staff members
- `POST /api/staff/onboard-instructor/` - Hire new instructor
- `POST /api/staff/activate-instructor/` - Create instructor account
- `GET /api/staff/credential-distribution/` - List unclaimed staff credentials

**Role Management (Tenant):**
- `GET /api/roles/` - List roles in current school
- `POST /api/roles/` - Create custom role
- `PUT /api/roles/{id}/` - Update role permissions
- `GET /api/roles/permissions/` - List all available permissions

**Academics (Tenant):**
- `GET/POST /api/academics/programs/` - Manage academic programs
- `GET/POST /api/academics/academic-levels/` - Manage grade levels
- `GET/POST /api/academics/sections/` - Manage class sections
- `GET/POST /api/academics/subjects/` - Manage subjects

**Course Content (Tenant):**
- `GET/POST /api/course-content/contents/` - Manage assignments, notes, etc.
- `POST /api/course-content/submissions/` - Submit assignments
- `POST /api/course-content/submissions/{id}/grade/` - Grade submissions
- `GET /api/course-content/submissions/` - List submissions for grading

---

## Environment Configuration

Required `.env` variables:

**Database:**
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`

**Environment identity and migrations:**
- `EDUSEKAI_ENV` - optional label used in the database application name
- `EDUSEKAI_EXPECTED_DATABASE` - `name@host:port`; warned about at startup and required to apply migrations
- `RUN_MIGRATIONS_ON_START` - Docker only; `true` (exactly) applies migrations at container start (default: off)

**Authentication:**
- `SECRET_KEY` - Django secret for signing tokens
- `ACCESS_TOKEN_LIFETIME_MINUTES` - JWT access token duration
- `REFRESH_TOKEN_LIFETIME_DAYS` - JWT refresh token duration

**Superuser:**
- `SUPERUSER_EMAIL` - Auto-created admin account email
- `SUPERUSER_PASSWORD` - Auto-created admin account password

**Payment Gateway:**
- `ESEWA_CLIENT_ID`, `ESEWA_CLIENT_SECRET`, `ESEWA_PRODUCT_CODE`

---

## Tech Stack

- **Framework:** Django 5.x with Django REST Framework
- **Database:** PostgreSQL 15-Alpine
- **Multi-Tenancy:** `django-tenants` for schema routing
- **Authentication:** PyJWT with HttpOnly cookie storage
- **Password Security:** Django's PBKDF2 hasher
- **Containerization:** Docker + Docker Compose

---

## Scaling Considerations

**Current Capacity:** 1,000+ schools, 100,000+ students

**Bottleneck Mitigation:**
- Connection pooling enabled (`CONN_MAX_AGE`)
- N+1 queries eliminated through bulk fetching
- Strategic database indexes on hot paths
- Atomic transactions to prevent data inconsistencies

**Future Scaling Path:**
- PostgreSQL read replicas for reporting workloads
- Redis caching layer for role/permission lookups
- Database sharding (move tenant schemas to separate servers)
- Horizontal application scaling (multiple Gunicorn workers behind load balancer)

---

**Last Updated:** January 2026  
**Architecture Version:** 2.0 (Tenant-Scoped RBAC)
