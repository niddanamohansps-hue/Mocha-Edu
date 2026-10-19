# Phase 1.2B — Academic Year API Report

## 1. Baseline git status
Recorded before any change: 35 entries (prior phases' work, all preserved).

## 2. Architecture inspected
- **ViewSets:** `academics` uses `ModelViewSet` with action-based `get_permissions()` returning `IsAuthenticated` plus `HasPermission(codename)`. The new viewset follows this exactly.
- **Routing:** `DefaultRouter` in `academics/urls.py`, mounted at `/api/academics/`. The new resource is registered on the same router.
- **Serializers:** `ModelSerializer` with `validate()` and field-level `validate_*` hooks.
- **Pagination:** `core.pagination.StandardResultsPagination` (page size 20, max 100), used across the project.
- **Audit:** `core.audit.log_action(request, action, model_name, object_id, changes)`. Best-effort: it never raises, so a logging failure can't block a business write.
- **Tenant isolation:** schema-per-tenant. The queryset only sees the current school's table.
- **Authentication:** `JWTCookieAuthentication` (global). Endpoints require `IsAuthenticated`.

## 3. API endpoints implemented
Base: `/api/academics/academic-years/`

| Method | Path | Behaviour | Permission |
|---|---|---|---|
| GET | `/` | List (paginated). Optional `?is_current=true\|false` | `view_academic_level` |
| POST | `/` | Create (never current; `is_current` is ignored on input) | `add_academic_level` |
| GET | `/{id}/` | Retrieve | `view_academic_level` |
| PATCH | `/{id}/` | Partial update of name/dates | `change_academic_level` |
| PUT | `/{id}/` | Full update (same rules) | `change_academic_level` |
| DELETE | `/{id}/` | Delete. Refused for the current year (400) | `delete_academic_level` |
| POST | `/{id}/set-current/` | Atomically makes this the single current year | `change_academic_level` |

## 4. Authentication behaviour
Every endpoint requires an authenticated user through the existing cookie JWT. Unauthenticated requests return 401 or 403 (the project's standard DRF response). Tests cover list, create, retrieve, update, and set-current without credentials.

## 5. Tenant-isolation approach
The queryset is `AcademicYear.objects.all()` evaluated inside the request's tenant schema. A year from another tenant doesn't exist in this schema, so retrieve, update, set-current, and delete on it return **404**. The same 404 is returned for "not in this tenant" and "does not exist", so cross-tenant existence is not revealed. Tests confirm that a privileged user is still isolated.

## 6. RBAC / permission behaviour
**Chosen codenames:** the existing `view/add/change/delete_academic_level` family. No new codename was added.

**Why:** academic years are academic-structure data, the same category as levels, sections, and subjects. The seeded permission catalogue already contains that family, so no migration or seed change was needed. Inventing a new codename would have required changing the permission seed for no gain.

**Mapping:** `set-current` uses the change permission, since it modifies a year. Delete uses the delete permission.

**Tested:** a manager holding the four codenames can create, update, set current, and delete. A reader holding only `view_academic_level` can list and read, but receives 403 on create, update, set-current, and delete.

## 7. Serializer validation
- **Name:** must be `YYYY-YY` with consecutive years, per the model's `clean()`. Rejected: `2026`, `2081`, `2026-2027`, `2026-28`, `abc`. Nothing is repaired.
- **Dates:** `start_date < end_date`, checked by the model's `clean()`, which the serializer calls. Equal or reversed dates return 400 on `end_date`.
- **Duplicate name in the same tenant:** a `name` validation error (400), checked explicitly by the serializer before the database constraint would fire.
- **`is_current` is read-only** on the serializer. A client cannot create or update a current year directly; only `set-current` can make one current.

## 8. Current-year transaction design
`set-current` runs in one `transaction.atomic()` block:
1. Lock the existing current row(s) with `select_for_update()`, excluding the target.
2. Clear `is_current` on them.
3. Set `is_current=True` on the target.

If the target is already current, the call returns 200 without writing (idempotent). A second concurrent request sees a consistent state after the first commits.

## 9. Concurrency / race-condition handling
PostgreSQL's partial unique index on `is_current WHERE is_current` is the final invariant. If two requests race and both try to make a different year current, the database rejects the second write with `IntegrityError`. The view catches `IntegrityError` inside the atomic block and returns **409 Conflict** with a generic message ("Another academic year was set as current at the same time. Please retry."). The raw database error is never returned.

`select_for_update()` narrows the race window but does not close it: under PostgreSQL's default isolation, two transactions can both see no current row and both try to insert one. The unique index is what guarantees the outcome, which is why it exists. The race test simulates the conflict and confirms the response is 409 and does not leak internal text.

## 10. Delete behaviour
Supported, with one restriction: deleting the **current** year is refused with 400 (`"The current academic year cannot be deleted. Set another year as current first."`). This prevents a tenant from being left with no current year through an API call.

Deletion of a non-current year is allowed. Phase 1.2A chose `on_delete` for dependent data as a future concern: no other table references `AcademicYear` yet (all year references are still free-text strings), so deleting a year cannot orphan a foreign key. When the later FK migration happens, `PROTECT` should be decided then.

## 11. Audit logging decision
Audited with `log_action`:
- `academic_year_created`
- `academic_year_updated`
- `academic_year_deleted`
- `academic_year_set_current`

Each records the year's name (and dates for create/update) in `changes`. The helper is the project's existing best-effort audit mechanism; no second system was introduced.

## 12. Pagination / filtering
- List uses `StandardResultsPagination` (page size 20, `?page_size=` up to 100).
- Filter: `?is_current=true` (also `1`/`yes`) or `false`. Implemented in `get_queryset()`, not a `FilterSet`, to match the simple filters elsewhere in `academics`. No search or ordering beyond the model's `Meta.ordering` (newest start date first).

## 13. Tests added
`academics/tests.py`, class `AcademicYearApiTests` (appended):
- Authentication: unauthenticated list, create, retrieve, update, set-current rejected.
- Tenant isolation: list shows only own years; cross-tenant retrieve, update, set-current, and delete return 404; same name allowed in another tenant; a privileged user is still isolated.
- Create: valid creation succeeds and is not current; `is_current` in the body is ignored; invalid name formats rejected; invalid dates rejected; duplicate name rejected.
- Update: authorized update succeeds; invalid update rejected.
- Current year: set-current switches and leaves exactly one current; set-current is idempotent; the current year cannot be deleted; a direct ORM write creating a second current year fails at the database; a simulated race returns 409 without leaking internal text.
- RBAC: reader can view but not mutate (403 on every write); privileged user isolated.
- Existing data safety: a legacy `StudentLevel` with `academic_year="2026"` is unchanged after API create and set-current.

## 14. Test results
- `manage.py test academics.tests.AcademicYearApiTests academics.tests.AcademicYearModelTests --keepdb`: **32 run, 32 passed** (13 model tests from Phase 1.2A, 19 API tests).

## 15. Regression results
`manage.py test payments academics course_content attendance core organizations staff profiles --keepdb`: **190 run, 190 passed**, 1,230.8 s.

This includes the Phase 0 payment tests, the Phase 0.4 academics, staff, profiles, and organizations tests, and the Phase 1.1 attendance and bulk-enrollment tests.

Not run: `students`, `examinations`, `fees`, `timetable`, `parent_portal`, `dashboard`, `families`, `notifications`, `roles`, `accounts`. None of their code changed in this phase, but they were not re-executed.

The log contains a `core_auditlog does not exist` traceback. It comes from an existing `core` test that deliberately forces `log_action` to fail, to prove audit logging never breaks a request. It is expected and does not indicate a failure.

## 16. `manage.py check`
`System check identified no issues (0 silenced).` — **PASS**. `makemigrations --check` reported no pending migrations, so no migration was added.

## 17. API verification results
Verified through the real HTTP endpoints in the test suite (not direct service calls):
- List returns only the current tenant's years (verified by ID set).
- Create, retrieve, update, and set-current work and return the serialized year.
- Tenant isolation: every cross-tenant operation returns 404.
- RBAC: every write by a reader returns 403; a manager succeeds.
- Invalid input returns controlled 400 with field-keyed messages.
- Race conflict returns 409 with a generic message; no raw database error reaches the client.

Not performed: manual HTTP testing against a running server. All checks ran through Django's test client against the test database.

## 18. Existing academic-year data unchanged
Confirmed by the `test_legacy_academic_year_strings_are_not_touched_by_the_api` test: a `StudentLevel` created with `academic_year="2026"` is still `"2026"` after creating a year and switching the current year. No backfill, normalization, or data change occurred. The dev database was not modified by this phase (no migration, no writes).

## 19. Files changed
- `backend/academics/serializers.py` — added `AcademicYearSerializer`; added `AcademicYear` and `DjangoValidationError` imports.
- `backend/academics/views.py` — added `AcademicYearViewSet`; added imports for `IntegrityError`, `transaction`, `timezone`, `status`, `action`, `Response`, `log_action`, `StandardResultsPagination`, `AcademicYearSerializer`, `AcademicYear`.
- `backend/academics/urls.py` — registered `academic-years` on the router.
- `backend/academics/tests.py` — appended `AcademicYearApiTests`.

Created: this report.

## 20. Files intentionally not changed
- No models or migrations (Phase 1.2A's model is used as-is).
- No student, attendance, examination, fee, course-content, timetable, or parent-portal file.
- No existing academic-year CharField or value. No ForeignKey added.
- No frontend file (no AcademicYear UI, no selector changes).
- Neither seeder.
- No permission or role seed (existing codenames reused).
- No existing `academics` endpoint behaviour changed.

## 21. Limitations
- **Free-text strings still drive every module.** Students, attendance, exams, fees, timetable, and course content still store free-text years. The API manages the table, but nothing reads from it yet.
- **Current year is not used by any other module.** Dashboards and filters still default to nothing, so `set-current` has no effect outside this API until the FK migration.
- **Race handling depends on the database index.** The 409 path was verified with a simulated conflict. A genuine two-request race was not exercised against concurrent transactions in tests.
- **Overlapping date ranges are still allowed.** Not added in Phase 1.2A; not added here.
- **Calendar scope.** Only `YYYY-YY` is accepted; Bikram Sambat and other calendars remain unsupported.
- **Delete of non-current years is unrestricted** while no FKs exist. This will need a deliberate decision (`PROTECT`) before the FK migration.
- **Pagination is the project default.** No search, no ordering parameter.

## 22. Follow-up recommendations
1. Decide `on_delete` behaviour (PROTECT recommended) before converting any string field to a ForeignKey.
2. Phase 1.2C (or the mapping phase): build the human-reviewed `"2026"` ↔ `"2026-27"` mapping for each tenant before any backfill.
3. Add an overlap rule once product confirms school-year boundaries.
4. Add a concurrent-request test using two real database connections to exercise the race path directly.
5. Expose `?is_current=true` as the default selector source for the frontend, once the frontend is migrated.
6. Run the full project suite once the remaining apps (`students`, `examinations`, `fees`, `timetable`, `parent_portal`, `dashboard`) are next touched.
