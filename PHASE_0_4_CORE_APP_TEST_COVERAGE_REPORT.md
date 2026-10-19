# Phase 0.4 — Core App Test Coverage Report

## 1. Scope
Tests were added for the four apps the module-gap audit found without meaningful coverage:
- `academics`
- `staff`
- `profiles`
- `organizations`

Each app's `tests.py` was an empty three-line stub. Every test below is new. Test conventions follow `examinations/tests.py`: Django `TransactionTestCase` with a per-class tenant schema, users created in the public schema, and real login through `/api/auth/login/` with the `HTTP_HOST` header. No new framework or factory library was introduced.

## 2. Existing Coverage Assessment

| App | Before | Prioritized |
|---|---|---|
| academics | 0 tests | RBAC on every write, uniqueness rules, relationship filtering, tenant isolation |
| staff | 0 tests | RBAC, duplicate employee IDs, read-only fields, instructor onboarding, portal-activation rules, tenant isolation |
| profiles | 0 tests | Self-only access (IDOR), validation, per-school profile separation, institution-profile permissions |
| organizations | 0 tests | Tenant lookup, Domain integrity, registration duplicate checks |

Indirect coverage from other apps (notably the examinations and payments tenant-isolation tests) was not counted for these four apps.

## 3. Tests Added

**academics — 12 tests** (`academics/tests.py`)
- Auth and RBAC: unauthenticated rejected; no-permission user blocked; view-only user can read but not create; owner can create.
- Validation and uniqueness: duplicate program code; duplicate level within program; duplicate section within level; subject code unique per level but reusable across levels; one instructor per subject per section.
- Relationships: section listing carries level and program names; assignment filter by section returns only that section.
- Tenant isolation: a program created in another school does not appear in this school's list.

**staff — 13 tests** (`staff/tests.py`)
- Auth and RBAC: unauthenticated rejected; no `view_staff` blocked; viewer can list but not create; manager can create.
- Validation and update: duplicate employee ID rejected; PATCH updates designation and profile name; `employee_id` is read-only and cannot be changed.
- Instructor onboarding: creates a linked Instructor record with an `INS-` employee ID; requires `add_staff`.
- Portal activation: `instructor` and `student` roles rejected; **`owner` role rejected (regression test, see §4)**; valid role creates the account and role assignment; requires `activate_staff_portal`.
- Tenant isolation: a staff member in another school is not listed.

**profiles — 12 tests** (`profiles/tests.py`)
- `/me/`: unauthenticated rejected; returns only the caller's profile; PATCH updates own profile; overlong name rejected (51 characters); **IDOR check**: `id`/`user_id` in the body cannot target another user's profile; first access creates a profile linked to the user; the same user gets separate profiles in two schools.
- Institution profile: requires `view_institution_profile`; name read from the tenant; PATCH requires `change_institution_profile`; editor's changes persist, including the name written to the Organization row; each school returns its own institution profile.

**organizations — 10 tests** (`organizations/tests.py`)
- Check-domain: missing parameter returns 400; full hostname, bare subdomain, and case-insensitive lookups succeed; unknown domain returns false; endpoint is public.
- Domain integrity: one hostname cannot map to two tenants (database constraint).
- Registration validation: existing subdomain, taken username, and short password all rejected before any tenant is created.

## 4. Security Coverage

| Area | Status | Evidence |
|---|---|---|
| Authentication | Covered | Unauthenticated requests rejected in academics, staff, profiles |
| RBAC | Covered | Academics writes, staff create/activate, institution read/write, check-domain public |
| Tenant isolation | Covered | Academics (programs), staff (members), profiles (institution profile and per-school profile) |
| IDOR | Covered for `/me/` | Body-supplied identifiers ignored; no ID in the URL |
| Portal-role escalation | Covered, **defect fixed** | `owner` was not blocked in `StaffActivationSerializer` (see below) |

Not covered: the **student** profile endpoints. Those live in the `students` app, which is outside this phase's scope.

## 5. Test Results

| Command | Result |
|---|---|
| `manage.py check` | Passed (no issues) |
| `manage.py test academics --keepdb` | 12 run, all passed (after fixing fixture bugs) |
| `manage.py test staff --keepdb` | 13 run, all passed (after one production fix and fixture corrections) |
| `manage.py test profiles --keepdb` | 12 run, all passed |
| `manage.py test organizations --keepdb` | included in the combined run |
| `manage.py test academics staff profiles organizations payments --keepdb` | **63 run, 63 passed, 0 failed** |

The 63 combined tests comprise 12 academics + 13 staff + 12 profiles + 10 organizations + 16 payments. The payments tests are the Phase 0.1 and 0.2 regression tests, and all still pass.

Full-project regression was **not run**. Each tenant-schema suite takes several minutes, and the scope of this phase is these four apps plus payments. The realistic-seeder tests (`core.tests.SeedRealisticSchoolCommandTest`) were not re-run in this phase.

**Test-infrastructure notes**
- Early runs failed in `setUp` and left orphaned tenant schemas. `tearDown` does not run when `setUp` raises. The fix is `addCleanup`, which runs regardless. Debris was removed from the **test** database (`test_edusekai_db`) directly.
- Two fixture bugs: `Role` slugs are unique and not auto-generated, so custom roles need explicit unique slugs; and global usernames carry a random suffix, so lookups must use `username__startswith`.

## 6. Coverage
Coverage tooling was not measured in this phase. No coverage figure is reported.

## 7. Production Code Changes

One genuine defect was fixed, with a minimal change:

- **File:** `backend/staff/serializers.py`
- **Change:** `StaffActivationSerializer.validate_role_slug` now also blocks `owner`: `["instructor", "student"]` became `["instructor", "student", "owner"]`.
- **Why:** The serializer's own comment says owner is blocked, but the code did not block it. Any user with `activate_staff_portal` could create an account holding the `owner` role, which grants every permission. The regression test `test_activation_rejects_owner_role` demonstrated this (it returned 201 before the fix).
- **Scope:** one line. The API response shape and all other role handling are unchanged.

No other production code was modified.

## 8. Database
No database changes to any schema. Test databases were created and cleaned as part of normal test runs. The earlier debris cleanup touched only `test_edusekai_db`.

## 9. Migrations
No migrations.

## 10. Git
- No commit, no push.
- No destructive commands used.
- Existing working-tree changes preserved. Only test files, the single staff serializer line, and this report were changed in this phase.

## 11. Remaining Gaps
- **Staff:** `StaffOnboardingView` (non-teaching onboarding), `CredentialDistributionView`, `InstructorViewSet` CRUD, and `StaffMember` delete behavior are not covered. Delete cascades into attendance and other apps were not examined.
- **Academics:** `SubjectAssignment` update/delete, `AcademicLevel`/`Section`/`Subject` update and delete, and delete cascades (for example, deleting a section with attendance or exam history) are not covered.
- **Profiles:** `InstitutionProfile` creation edge cases and invalid media uploads are not covered.
- **Organizations:** tenant provisioning itself (`RegisterOrganizationView` end to end) is not covered, because each run creates and migrates a schema. This is best handled in a dedicated, slower suite.
- **Academic year** remains a string convention. Tests document current behavior only and do not model it.

## 12. Recommendations
1. **Check-domain enumeration.** `CheckDomainView` is public and reveals whether any school subdomain exists. This is intentional for the signup flow, but it is an enumeration risk. Consider rate limiting it, or returning a generic response. Not asserted or changed here.
2. **Access tokens survive password reset** (already documented in the Phase 0 audit). Remains open.
3. **Add delete-cascade tests** for academics and staff before any destructive admin feature is built.
4. **Add a slow-suite tier** for tenant provisioning, so the fast suites stay quick.
5. **Measure coverage** with `coverage run manage.py test` once the four apps are stable, to establish a baseline.
