# Announcements/Communication Module — Implementation Plan (Revision 5)

**Status: backend implemented (Phases 1–4) and tested against the isolated test database. The migration has NOT been applied to any development or production database. No frontend has been built. See §17, "As Built", for what exists and how to deploy it.**

**Revision 5 changes**: records the implementation. Adds §17 (as-built behavior, endpoints, permissions, scheduling, deployment, test results, limitations), updates this status line and the closing note, and corrects the scheduled-publish and broadcast code sketches to the implemented `Announcement.Status.SCHEDULED` / `publish_announcement(announcement.id)` forms. Earlier sections are kept as the design record; where they differ from §17, §17 describes the code.

**Revision 4 changes**: documentation-only corrections from the Phase 0 preflight, no implementation. (1) Empty audience, decided as Option A: publishing to an audience that resolves to zero eligible recipients is rejected with HTTP 400 before any write; the announcement stays unpublished; covered by the new `AnnouncementEmptyAudienceTest` and an acceptance criterion. (2) The `broadcast_announcements` check moves out of `get_permissions()` into the `publish` action after `get_object()`, since `HasPermission` is request-level only and the audience isn't known before the object is loaded. (3) Permission seeding documents the verified `post_migrate` mechanism (`roles/signals.py`); the three permissions will be appended to `SYSTEM_PERMISSIONS` in Phase 1, with no separate data migration. (4) "Two new permission codenames" corrected to three. (5) Only the `owner` role receives the permissions automatically; other roles need a grant through role management; acceptance criteria updated.

**Revision 3 changes**: documentation-only corrections, no design change. (1) The migration and rollback section now states that `0001_initial.py` creates both `Announcement` and `AnnouncementRecipient`, including the `(announcement, user_id)` uniqueness constraint, and rollback covers both tables. (2) Phase 2's `resolve_recipients` description is aligned with the Audience Resolution section: scalar `user_id` values collected into one deduplicated `set`, then one batched `accounts.User` email lookup. (3) The test matrix adds `AnnouncementTransactionRollbackTest` for atomic rollback of publication database writes, kept distinct from post-commit dispatch failure testing (`AnnouncementDeliveryFailureTest`).

**Revision 2 changes**: resolves five review issues raised against the initial plan, each verified against actual code in this revision (not assumed or guessed). (1) The publication-transaction claim is corrected: `notify_many()`'s `bulk_create()` and `queue_email()`'s `EmailOutboxEvent` write are both plain synchronous DB writes that genuinely roll back together with the status-flag flip inside one `transaction.atomic()` block — but the Celery *dispatch* itself is deferred via `transaction.on_commit()` and, on failure, deliberately does NOT roll back anything (the business operation already committed); this distinction is now stated precisely rather than claimed as a single "all side effects roll back together" guarantee. (2) Scheduled publishing's tenant-discovery design is corrected after finding that the cited precedent (`recover_stale_outbox_events`) does **not** actually isolate per-tenant failures (no try/except in its loop) and does **not** filter on `Organization.is_active` (confirmed via direct read of `organizations/models.py` — the field exists but the precedent ignores it) — the new task is now specified to improve on this, not copy it uncritically. (3) Recipient-resolution relation paths (`student__profile`, `parent__profile`, `staff.profile`) are confirmed correct by direct model reads; `profiles.Profile.user_id` is confirmed to have **no database uniqueness constraint** (verified: only a composite index with `local_username`, no `unique=True`), meaning two `Profile` rows could in principle reference the same account — this is now stated as a real, previously-unverified data-integrity gap, not assumed away. (4) The `mine/` endpoint now uses a persisted recipient snapshot (`AnnouncementRecipient`), not dynamic audience re-evaluation, per the review's own recommendation. (5) Lifecycle and permission-seeding questions are answered with explicit recommendations (still flagged for product-owner confirmation, not silently decided). The canonical email-authority question is also resolved: `accounts.User.email` is confirmed the single, only source of email anywhere in the codebase — there is no second, possibly-disagreeing email field to reconcile.

This plan follows two prior read-only reviews in this engagement:
- `EDUSEKAI_COMPLETE_MODULE_GAP_ANALYSIS.md` — identified Communication/Announcements as the recommended next feature (lowest dependency risk, purely additive on existing tested infrastructure).
- A read-only architecture scoping review (A–J sections) that verified `notify_many()`, the `EmailOutboxEvent` outbox, Celery Beat wiring, and the absence of any existing `Announcement` model, each against exact file:line citations.
- A follow-up, directly-verified (by this session, not a subagent) email-resolution investigation confirming the exact cross-schema pattern to reuse.

This work remains entirely separate from the AcademicYear FK migration (`backend/academics/backfill.py`, `PHASE_1_3B_*` files). **Stage B of that work remains unauthorized and untouched by this plan.**

## Decisions Carried Into This Plan (settled in prior review, not reopened here)

| Decision | Settled value |
|---|---|
| New app vs. extending `notifications` | New tenant app `backend/announcements/`, calling into `notifications.services` as a library — never modifying that app's internals. |
| Email-address resolution | Reuse the exact pattern in `examinations/services.py:465-494` (`_resolve_result_notification_recipients`): resolve `Profile.user` (the existing `profiles/models.py:61-72` soft-link property), skip silently if no linked account or no email — never error, never invent a new contact field. |
| Read acknowledgements | Excluded from MVP. `Notification.is_read` already exists and is reused as-is for the in-app inbox; no "seen the announcement itself" tracking is added. |
| Expiry / auto-archive | Deferred — no precedent anywhere in the codebase (`Examination.is_published` is a one-way flag with no expiry concept); not designed in this plan. |
| School-wide broadcast permission | A distinct `broadcast_announcements` permission codename is required for `audience_type=ALL`, separate from `manage_announcements` (which governs scoped announcements: a single section, level, or role group). |
| Recipient deduplication across overlapping audiences | **Designed explicitly in this plan (§ Audience Resolution), not assumed harmless** — see below. This is the one item flagged for explicit design rather than inherited as "duplicates are fine." |
| AcademicYear Stage B | Remains unauthorized and untouched. |

## Evidence Basis (verified directly in this engagement, with file:line citations)

- `notifications.services.notify_many(*, recipient_user_ids, title, body, category, link)` — `backend/notifications/services.py:38-66`. Bulk-creates `Notification` rows; its own docstring states duplicate recipient IDs are tolerated as harmless at that layer.
- `notifications.services.queue_email(*, to_email, subject, body)` — `backend/notifications/services.py:69-121`. Writes one `EmailOutboxEvent` row, dispatches via `transaction.on_commit()`, captures `connection.schema_name` explicitly for the Celery worker.
- `EmailOutboxEvent` state machine — `backend/notifications/models.py:52-119`: `PENDING → RETRYING → SENT|FAILED`, with `ErrorType` (`TEMPORARY`/`PERMANENT`), `attempts`/`max_attempts` (default 3), `next_attempt_at`.
- `send_outbox_email` — `backend/notifications/tasks.py:44-128`: idempotent against duplicate/late dispatch (returns immediately if already `SENT`/`FAILED`), exponential backoff capped at 900s.
- `recover_stale_outbox_events` — `backend/notifications/tasks.py:131-168`, wired into `CELERY_BEAT_SCHEDULE` at `backend/config/settings.py:302-307` (every 10 minutes).
- `TENANT_APPS`/`SHARED_APPS` — `backend/config/settings.py:44-82`. `notifications`, `students`, `staff`, `families`, `profiles`, `academics` are tenant-scoped; `accounts` (and therefore `accounts.User.email`) is shared/public-schema.
- `Profile.user` cross-schema resolution — `backend/profiles/models.py:61-72`: `User.objects.filter(id=self.user_id).first()`, safe because `accounts` is `SHARED_APPS` and requires no `schema_context()` switch (that mechanism is only needed for Celery tasks with no request-bound tenant context).
- `HasPermission(codename)` RBAC — `backend/roles/permissions.py:4-83`; usage convention at `backend/examinations/views.py:38-56` (`get_permissions()` branching by `self.action`).
- `Examination.is_published`-style immutability-after-publish — `backend/examinations/views.py:65-70` ("a published examination cannot be edited") — the precedent this plan's `PUBLISHED`-is-immutable rule follows.
- Zero `Announcement` model/view/migration exists anywhere (`grep -r "Announcement" backend/` — no hits outside this plan).
- No existing model carries an email field other than `accounts.User.email` (`accounts/models.py:10`) — confirmed by direct read of `accounts/models.py`, `profiles/models.py`, `students/models.py`, `families/models.py`, `staff/models.py`.

## Audience Resolution: Explicit Deduplication Design (revised)

Flagged in review as needing explicit design rather than inherited "duplicates are harmless," and specifically requiring verification of the underlying relation paths and identity guarantees before being trusted. Verified directly in this revision:

- **Relation paths confirmed correct** (all read directly, not assumed): `students.StudentLevel.student` → `students.Student.profile` (`OneToOneField` to `profiles.Profile`, `related_name="student_record"` — `students/models.py:11-13`); `families.Parent.profile` (`OneToOneField`, `related_name="parent_record"` — `families/models.py:10-12`); `staff.StaffMember.profile` (`OneToOneField`, `related_name="staff_record"` — `staff/models.py:11-13`). So `select_related("student__profile")` and `select_related("parent__profile")` are valid paths against the real schema, not a guess.
- **Canonical identity for dedup**: the account's `user_id` (the value on `Profile.user_id`) is the dedup key — never the `Profile` row's own `id`, and never email-string equality. This matters because of the next point.
- **A real, previously-unverified gap, now stated honestly**: `profiles.Profile.user_id` (`profiles/models.py:17`) is a plain `UUIDField(db_index=True, null=True, blank=True)` with **no uniqueness constraint** — the only index involving it is a composite `(user_id, local_username)` index (`profiles/models.py:52-55`), not a `unique=True`. **It is structurally possible today for two different `Profile` rows (e.g. a `Student` profile and an unrelated `StaffMember` profile) to reference the same `user_id`** — nothing in the schema prevents it. This plan does not attempt to fix that data-integrity gap (out of scope — it predates this feature and affects more than just Announcements), but the resolver must be written knowing it exists: deduping by `user_id` is correct and necessary specifically *because* this isn't otherwise guaranteed unique at the `Profile` level.
- **Why email resolution stays unambiguous despite that gap**: email is never read from `Profile` — it is looked up exactly once per canonical `user_id` directly against `accounts.User.email` (`accounts/models.py:10`), which **is** the single, only source of email anywhere in this codebase (confirmed by direct read of `accounts/models.py`, `profiles/models.py`, `students/models.py`, `families/models.py`, `staff/models.py` — no other model has an email field). So even if two `Profile` rows somehow shared a `user_id`, there is still exactly one `accounts.User` row and exactly one authoritative email for that `user_id` — the ambiguity, if it ever occurred, would be about which `Profile`'s *name/display data* to show, never about which email to send to. This is a narrower, already-contained risk, not an open question for this feature.
- **In-app (`notify_many`)**: harmless by the function's own documented contract (confirmed by direct read, `notifications/services.py:38-66` — `bulk_create()`, no uniqueness enforced, explicitly documented as tolerating duplicates) — no change needed, but the resolver still deduplicates before calling it, to keep delivery counts/logs meaningful and avoid confusing a recipient with two identical inbox rows for one announcement.
- **Email (`queue_email`)**: **not harmless** — two overlapping audience rules resolving to the same canonical `user_id` (e.g. a user who is both a `StaffMember` and a parent of a student in the targeted section) must not receive two identical emails. The resolver builds a single `{user_id: email}` dict before any `queue_email()` calls — one call per unique `user_id`, never per audience-rule-match.
- **Design**: `resolve_recipients(announcement) -> dict[UUID, {"user_id": UUID, "email": str | None}]` — a single de-duplicated mapping, built by unioning every matching audience-rule's resolved `Profile.user_id` set first (a plain Python `set()` of UUIDs, collected across all matching `StudentLevel`/`StudentParentRelation`/`StaffMember` queries before any email lookup happens), then resolving each unique `user_id` to its `accounts.User` exactly once via a single `User.objects.filter(id__in=<the deduplicated set>).values("id", "email")` query (one query for the whole batch, not one per recipient — avoiding the N+1 pattern already flagged elsewhere in this codebase's gap analysis). This guarantees one `Notification` row and at most one `EmailOutboxEvent` row per canonical account per announcement, regardless of how many audience rules they match or how many `Profile` rows might (per the gap above) reference them.

## Phase 0 — Architecture and Preflight (Read-Only)

**Goal**: confirm every dependency this plan relies on still holds, before any code is written.

- Re-verify `TENANT_APPS` includes `notifications`, `students`, `staff`, `families`, `profiles`, `academics` (confirmed above; re-check immediately before Phase 1 starts in case of drift).
- Re-verify `notify_many()` and `queue_email()` signatures are unchanged from the citations above.
- Re-verify `HasPermission` and the `get_permissions()`-by-action convention are unchanged.
- Confirm the test harness pattern (`TransactionTestCase` + `tenant_context`, per `examinations/tests.py`) still applies without modification.
- **Blocker check**: if any of the above has changed since this plan was written, stop and re-scope before Phase 1 — do not proceed on stale assumptions.
- **Deliverable**: a short confirmation note (not a new document) appended to this plan before Phase 1 begins, or an explicit flag if something has drifted.

## Phase 1 — Data Model and Permissions

**New tenant app**: `backend/announcements/`, added to `TENANT_APPS` in `config/settings.py` immediately after `notifications`.

**Proposed files**:
- `backend/announcements/__init__.py`, `apps.py`
- `backend/announcements/models.py`
- `backend/announcements/migrations/0001_initial.py`
- `backend/announcements/admin.py` (register for Django admin, minimal)

**Model** (`Announcement`):

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | Matches project-wide convention. |
| `title` | `CharField(max_length=200)` | |
| `body` | `TextField()` | |
| `created_by_user_id` | `UUIDField(db_index=True)` | Soft link, same convention as `Notification.recipient_user_id` — never a FK to `accounts.User`. |
| `audience_type` | `CharField(choices=[ALL, ALL_STAFF, ALL_PARENTS, ALL_STUDENTS, SECTION, LEVEL])` | |
| `audience_section` | `ForeignKey("academics.Section", null=True, blank=True)` | Required iff `audience_type == SECTION`. |
| `audience_level` | `ForeignKey("academics.AcademicLevel", null=True, blank=True)` | Required iff `audience_type == LEVEL`. |
| `send_email` | `BooleanField(default=False)` | |
| `status` | `CharField(choices=[DRAFT, SCHEDULED, PUBLISHED, ARCHIVED], default=DRAFT)` | |
| `scheduled_at` | `DateTimeField(null=True, blank=True)` | |
| `published_at` | `DateTimeField(null=True, blank=True)` | |
| `created_at` / `updated_at` | auto | |

**New model, added in this revision — `AnnouncementRecipient` (persisted delivery snapshot)**: resolves issue #4 (the `mine/` endpoint needs a clear audience-membership rule). One row per `(announcement, user_id)` pair, written once at publish time, inside the same `transaction.atomic()` block as the rest of `publish_announcement()` (§Phase 2). This is the audit trail of "who this announcement was actually resolved to and when" — it does not re-evaluate dynamically. Rationale (per the review's own recommendation): a persisted snapshot is easier to audit and keeps historical delivery behavior predictable — if a student later moves out of the targeted section, their `mine/` list still correctly shows the announcement they were actually sent, rather than a view that silently changes after the fact based on current membership.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | |
| `announcement` | `ForeignKey(Announcement, on_delete=CASCADE, related_name="recipients")` | |
| `user_id` | `UUIDField(db_index=True)` | The canonical, deduplicated account ID (see Audience Resolution below) — never a `Profile` ID. |
| `email_sent` | `BooleanField(default=False)` | True iff a `queue_email()` call was actually made for this recipient (distinct from whether it was ever delivered — that remains `EmailOutboxEvent`'s own concern). |
| `created_at` | auto | |

`unique_together = ("announcement", "user_id")` — a second, DB-level dedup guarantee beyond the resolver's own in-memory dedup (§Audience Resolution), so even a resolver bug could not produce two rows for the same person on the same announcement.

`/api/announcements/mine/` (§Phase 3) queries `AnnouncementRecipient.objects.filter(user_id=request.user.id)` joined to `Announcement` — never re-running the audience resolver live, and never trusting any client-supplied identity beyond `request.user`.

**Lifecycle validation** (application-layer, in `clean()`/serializer `validate()`, mirroring `GradeBoundary.clean()`'s pattern of raising `ValidationError` on invalid combinations — `examinations/models.py`):
- `audience_type == SECTION` requires `audience_section` set, `audience_level` null (and vice versa for `LEVEL`); `ALL`/`ALL_STAFF`/`ALL_PARENTS`/`ALL_STUDENTS` require both null.
- Once `status == PUBLISHED`, `title`/`body`/`audience_*`/`send_email` become immutable — only `status` may transition forward (`PUBLISHED → ARCHIVED`). Enforced in the view layer (`perform_update`), mirroring `examinations/views.py:65-70`.
- `scheduled_at`, if set, must be in the future at creation time; `status` must be `SCHEDULED` iff `scheduled_at` is set and in the future.

**Permissions** (three new codenames, added via the existing `roles` seeding mechanism, verified in Phase 0):
- `view_announcements` — list/detail.
- `manage_announcements` — create/update (while `DRAFT`/`SCHEDULED`)/archive/publish to a *scoped* audience (`ALL_STAFF`, `ALL_PARENTS`, `ALL_STUDENTS`, `SECTION`, `LEVEL`).
- `broadcast_announcements` — required *in addition to* `manage_announcements` to publish with `audience_type == ALL`. A user with `manage_announcements` but not `broadcast_announcements` can create an `ALL`-audience announcement as a `DRAFT` but cannot publish it.

**How these permissions are provisioned (verified in Phase 0)**:
- Permissions are seeded by a `post_migrate` signal receiver, `seed_roles`, in `backend/roles/signals.py:5-74`. It runs when the `roles` app's `post_migrate` fires, skips the `public` schema, and `update_or_create`s every entry in `SYSTEM_PERMISSIONS` (`backend/roles/constants.py`) into the current tenant schema. It is idempotent.
- **Existing tenants** receive new permissions on the next `migrate_schemas` run, because `post_migrate` fires on every migrate run. **New tenants** receive them because `Organization.auto_create_schema = True` (`backend/organizations/models.py:20`) runs migrations at tenant creation, which fires the same signal.
- **The three announcement permissions are therefore added by appending three entries to `SYSTEM_PERMISSIONS` during the later implementation phase** (Phase 1), in the existing `codename`/`name`/`module`/`description` format. No separate permission data migration is planned; Phase 1's own `migrate_schemas` run seeds them into every tenant.
- **Default assignment: the signal automatically grants all permissions to the `owner` role only** (`roles/signals.py:73-74`). The other system roles (`staff`, `instructor`, `student`, `parent`) receive none of the announcement permissions automatically. A school must grant them to other roles through the existing role-management mechanism, `RoleViewSet` (`backend/roles/views.py`), which permits changing permissions on system roles. Superusers and the `owner` role also pass every `HasPermission` check regardless (`roles/permissions.py:20-21, 68-69, 78-79`).

**Migration and rollback strategy**:
- Single `0001_initial.py` containing:
  - a `CreateModel` operation for `Announcement`;
  - a `CreateModel` operation for `AnnouncementRecipient` (with its `ForeignKey` to `Announcement`, `on_delete=CASCADE`);
  - the database uniqueness constraint on `AnnouncementRecipient` for `(announcement, user_id)`.
  No data migration is needed, since both are new models with no legacy data.
- Rollback: reversing `0001_initial.py` drops both tables — `announcements_announcementrecipient` (and its `(announcement, user_id)` uniqueness constraint) and `announcements_announcement` — in dependency order, which Django's migration reversal handles automatically. This is safe at any point before Phase 2+ code or production data relies on either table (same discipline already established for the AcademicYear FK migrations in `PHASE_1_3B_IMPLEMENTATION_PLAN.md` §11 — reversible only while no later-phase code has built on it). Once `AnnouncementRecipient` holds real delivery snapshots, reversing the migration would discard that audit trail, so rollback at that point requires a reviewed decision, not a routine reversal.
- No second migration for permissions: the three permission rows are seeded by the existing `post_migrate` signal from `SYSTEM_PERMISSIONS` (see "How these permissions are provisioned" above), not by a data migration.

## Phase 2 — Audience Resolution and Delivery

**Proposed file**: `backend/announcements/services.py`

- `resolve_recipients(announcement) -> dict[UUID, {"user_id": UUID, "email": str | None}]` — implements the **Audience Resolution: Explicit Deduplication Design** section above exactly; this is a summary of that design, not a different one:
  1. **Collect scalar `user_id` values** from each applicable audience query — never `Profile` objects:
     - `ALL_STUDENTS` / `SECTION` / `LEVEL`: `students.StudentLevel.objects.filter(is_current=True, [section=X | level=Y]).values_list("student__profile__user_id", flat=True)`.
     - `ALL_PARENTS` (or parents implied by a student-scoped audience): `families.StudentParentRelation.objects.filter(student__in=<resolved students>).values_list("parent__profile__user_id", flat=True)`.
     - `ALL_STAFF`: `staff.StaffMember.objects.filter(is_active=True).values_list("profile__user_id", flat=True)`.
     - `ALL`: union of all of the above.
  2. **Combine IDs from all applicable audience rules into one Python `set`** (discarding `None`, i.e. profiles with no linked account) before any email resolution happens.
  3. **Duplicate `Profile` rows that reference the same canonical `user_id`** (possible, since `Profile.user_id` has no uniqueness constraint — see the Audience Resolution section) each contribute the same scalar value to that `set`, so they collapse to one recipient identity before `accounts.User` is ever queried. No `Profile` identity is carried past this step.
  4. **Resolve emails in one batched query**: `User.objects.filter(id__in=<deduplicated set>).values("id", "email")` — one query for the whole announcement, not one per recipient.
  5. **Skip** (don't error) any `user_id` with no matching `accounts.User` row or a blank `email` for email purposes, per the verified `_resolve_result_notification_recipients` precedent (`examinations/services.py:465-494`).
  6. **Delivery uses only this deduplicated mapping**: `AnnouncementRecipient` rows, the single `notify_many()` call, and the `queue_email()` calls are all driven from it — never once per audience-rule match.
- `publish_announcement(announcement, *, actor_user_id)`:
  - Guard: `if announcement.status == PUBLISHED: raise ValidationError(...)` (idempotency, mirroring `publish_examination`'s `is_published` guard).
  - Guard: if `audience_type == ALL`, caller must hold `broadcast_announcements`. This is checked in the view's `publish` action after `get_object()`, not in `get_permissions()` and not here (see §Phase 3); this function trusts it has already been authorized.
  - Guard (empty audience, decided in Revision 4: Option A): resolve recipients first, **before any database write**. If the deduplicated recipient set is empty, raise `ValidationError({"non_field_errors": ["No eligible recipients were found for this audience."]})`, which the view returns as HTTP 400. The announcement stays in its pre-publish status, and no `AnnouncementRecipient`, `Notification`, or `EmailOutboxEvent` row is written. "Eligible" means a resolved `user_id` exists for in-app delivery; an announcement whose audience has no linked accounts at all is rejected. This also avoids `notify_many()`'s own `ValueError` on an empty list (`notifications/services.py:51-52`). The check runs inside the same `transaction.atomic()` block, so even if it were reached after a write, nothing would persist.
  - Wrapped in `transaction.atomic()`: resolve recipients, set `status = PUBLISHED`, `published_at = now()`, create the `AnnouncementRecipient` rows, call `notify_many(...)` once with the full deduplicated `user_id` list, then (if `send_email`) call `queue_email(...)` once per unique resolved email.

  **Precise transaction/rollback guarantee (corrected in this revision — resolves issue #1)**: this plan's original wording claimed "all side effects roll back together" without distinguishing two genuinely different kinds of operation inside this one function. Verified directly against both services' actual code (`notifications/services.py:22-66, 69-121`):
  - **What genuinely rolls back together, confirmed**: the `status`/`published_at` flip, the `AnnouncementRecipient.objects.bulk_create(...)`, `notify_many()`'s `Notification.objects.bulk_create(...)` (a plain synchronous write, no Celery involvement — `notifications/services.py:38-66`), and `queue_email()`'s `EmailOutboxEvent.objects.create(...)` (also a plain synchronous write, explicitly **not** wrapped in try/except in the existing code specifically so a DB/validation error here propagates and rolls back the caller — `notifications/services.py:69-121`'s own docstring states this). All of these are ordinary database writes inside one `transaction.atomic()` block, so a failure in any one of them rolls back every other write in the same block, including the status flip. This part of the original claim is correct.
  - **What does NOT roll back, and is not supposed to**: `queue_email()` registers the actual Celery dispatch via `transaction.on_commit()` — meaning the `.delay()` call only happens *after* this whole block has already successfully committed. If that dispatch fails (a `CeleryError`/`KombuError`, e.g. the broker is briefly unreachable), `queue_email()`'s own code catches it and only logs a warning — by design, since the business operation (the announcement is published, the `EmailOutboxEvent` row exists, `AnnouncementRecipient` rows exist) has already committed and must not be undone by a dispatch hiccup. The affected `EmailOutboxEvent` row simply stays `PENDING` and is picked up later by `recover_stale_outbox_events` (see below). **This plan does not claim dispatch failures roll back anything — they cannot, because they happen after commit, and are handled instead by the existing retry/recovery machinery.**
  - Net effect, stated precisely: `publish_announcement()` is all-or-nothing **for its own database writes** (status, recipients, notification rows, outbox rows) — a true atomic unit. Whether the *email actually gets sent* is a separate, already-solved concern handled entirely by `EmailOutboxEvent`'s existing state machine and Celery retry policy, same as every other `queue_email()` caller in this codebase.
- **Scheduled publish** (Phase 3, not Phase 2): a periodic Celery Beat task, `announcements.tasks.publish_scheduled_announcements`, added to `CELERY_BEAT_SCHEDULE` alongside `recover-stale-outbox-events`.

  **Tenant-discovery design (corrected in this revision — resolves issue #2)**: the plan originally said this would "mirror `recover_stale_outbox_events`'s per-tenant-schema loop" without checking what that loop actually does. Direct re-read of `notifications/tasks.py:131-168` found two real gaps in that precedent, which this new task must **not** copy uncritically:
  1. **No per-tenant failure isolation**: `recover_stale_outbox_events`'s `for tenant in get_tenant_model().objects.exclude(schema_name="public"): with schema_context(...): ...` has no `try`/`except` around each tenant's block — an exception while processing one tenant (a transient DB error, a bad row) would propagate out of the whole task, skipping every tenant that would have been processed after it in iteration order. This is a real, pre-existing gap in the cited precedent, not a property of this plan's design.
  2. **No active-tenant filtering**: `get_tenant_model().objects.exclude(schema_name="public")` includes every tenant regardless of status, even though `organizations.Organization.is_active` (`organizations/models.py:15`, `BooleanField(default=True)`) exists and is simply not used by that query.

  **This plan's task is designed to improve on both points, explicitly**, not inherit them as if they were proven-safe:
  ```
  for tenant in Organization.objects.filter(is_active=True).exclude(schema_name="public"):
      try:
          with schema_context(tenant.schema_name):
              due = Announcement.objects.filter(status=Announcement.Status.SCHEDULED, scheduled_at__lte=now())
              for announcement in due:
                  publish_announcement(announcement.id)
      except Exception:
          logger.exception("publish_scheduled_announcements failed for tenant %s", tenant.schema_name)
          continue  # one tenant's failure must not block the rest
  ```
  - **Deleted tenants**: `Organization` rows are not physically deleted in this codebase's existing convention (confirmed by the `is_active` flag's existence as the deactivation mechanism) — a deleted/decommissioned tenant is expected to be `is_active=False`, which the `.filter(is_active=True)` above already excludes. No separate "handle a deleted schema" case is needed given this convention; if a schema were ever dropped while still marked active (a data-integrity violation of that convention, not an expected state), `schema_context()` would raise and the `try`/`except` above logs and continues rather than crashing the whole task.
  - **One tenant's failure never blocks others**: the `try`/`except continue` per tenant guarantees this — an explicit improvement flagged here specifically because the precedent does not have it.
  - This same per-tenant `try`/`except` isolation pattern should be considered as a candidate fix for `recover_stale_outbox_events` itself, but that is **out of scope for this plan** — a pre-existing gap in unrelated code, not something this feature should silently patch as a side effect.

**Failure recovery**: no new recovery mechanism needed — once `notify_many`/`queue_email` are called, failure handling is entirely the existing, already-tested `EmailOutboxEvent`/`send_outbox_email`/`recover_stale_outbox_events` machinery. `publish_announcement()` itself either fully succeeds (status flips, all notifications queued) or fully rolls back (status unchanged, nothing queued) — there is no partial-publish state to design for.

## Phase 3 — API and Security

**Proposed file**: `backend/announcements/views.py`, `serializers.py`, `urls.py`

| Endpoint | Method | Permission | Notes |
|---|---|---|---|
| `/api/announcements/` | GET | `view_announcements` | `PageNumberPagination` (page_size=20, max_page_size=100, matching `notifications/views.py:17-32`'s convention); `filterset_fields = ["status", "audience_type"]` via `DjangoFilterBackend`. |
| `/api/announcements/` | POST | `manage_announcements` | Creates as `DRAFT`. If `audience_type == ALL` is supplied, creation is allowed (draft-only) but publish will be blocked without `broadcast_announcements` (see below). |
| `/api/announcements/{id}/` | GET | `view_announcements` | |
| `/api/announcements/{id}/` | PATCH | `manage_announcements` | 400 if `status == PUBLISHED` (immutability guard, mirroring `examinations/views.py:65-70`). |
| `/api/announcements/{id}/publish/` | POST | `manage_announcements`, **and `broadcast_announcements` additionally required iff `audience_type == ALL`** (checked in the action after `get_object()`, see below) | Calls `publish_announcement()`. Returns HTTP 400 "No eligible recipients were found for this audience." if the audience resolves to zero recipients; the announcement stays unpublished. |
| `/api/announcements/{id}/` | DELETE | `manage_announcements` | Soft-transition to `ARCHIVED`, never a hard delete once any notification has been sent (DRAFT-only hard delete may be allowed — to be confirmed in Phase 0, not assumed). |
| `/api/announcements/{id}/cancel/` | POST | `manage_announcements` | New in this revision (resolves issue #5): `SCHEDULED → DRAFT`, clears `scheduled_at`. Not available once `PUBLISHED`. |
| `/api/announcements/mine/` | GET | `IsAuthenticated` only | **Revised in this revision**: queries the persisted `AnnouncementRecipient` snapshot (`.filter(user_id=request.user.id)`), never re-runs the audience resolver live — mirrors `notifications/views.py:35-49`'s "never trust client-supplied recipient, always filter by `request.user.id`" rule, extended here to also never re-derive membership dynamically (issue #4). |

`get_permissions()` branches by `self.action`, exactly matching `examinations/views.py:38-56`'s established pattern; for `publish` it requires `manage_announcements`.

**Broadcast check placement (corrected in Revision 4, verified in Phase 0)**: the `broadcast_announcements` check cannot live in `get_permissions()`. That method runs before the announcement is loaded, so its `audience_type` is unknown there, and `HasPermission` (`roles/permissions.py:4-83`) implements only request-level `has_permission()`, not object-level `has_object_permission()`. The check therefore runs inside the `publish` action, after `get_object()`:
```
announcement = self.get_object()
if announcement.audience_type == Announcement.AudienceType.ALL:
    if not HasPermission("broadcast_announcements").has_permission(request, self):
        raise PermissionDenied("Broadcasting to everyone requires the broadcast_announcements permission.")
publish_announcement(announcement.id)
```
This reuses `HasPermission` unchanged, so superuser bypass, owner bypass, and `?active_role=` handling behave exactly as for every other permission check.

**Tenant-isolation and security** (carried from the prior scoping review, restated here as acceptance criteria, not re-derived):
- No endpoint accepts a client-supplied recipient list — only `audience_type`/`audience_section`/`audience_level`. Resolution is entirely server-side, inside the authenticated request's tenant schema.
- All queries (`Announcement`, `StudentLevel`, `StudentParentRelation`, `StaffMember`, `Profile`) are tenant-scoped tables; cross-tenant leakage via the ORM is structurally prevented the same way it already is for every other tenant-scoped model in this codebase.
- The one genuine async risk: any future Celery task touching `Announcement` (e.g. the Phase 3 scheduled-publish task) must receive and enter `schema_context(schema_name)` explicitly, exactly like `send_outbox_email`/`recover_stale_outbox_events` already do — called out here as a Phase 3 implementation requirement, not optional.

## Phase 4 — Verification and Release Readiness

**Test file**: `backend/announcements/tests.py`, following the house style (`TransactionTestCase` + `tenant_context`, per `examinations/tests.py`).

| Test class | Covers |
|---|---|
| `AnnouncementModelTest` | Model creation; `clean()` validation (audience-field combinations); status-transition rules (`DRAFT→SCHEDULED→PUBLISHED→ARCHIVED` and `DRAFT→PUBLISHED` direct). |
| `AnnouncementImmutabilityTest` | PATCH rejected once `status == PUBLISHED`, mirroring `test_published_examination_cannot_be_edited`. |
| `AnnouncementAudienceResolutionTest` | Each `audience_type` resolves to the exact expected `user_id` set given seeded `StudentLevel`/`StudentParentRelation`/`StaffMember` fixtures; **explicit test that a user matching two audience rules (e.g. staff member who is also a parent) is deduplicated to exactly one `Notification` and one `EmailOutboxEvent`** — this is the specifically-flagged dedup design, tested directly, not assumed. |
| `AnnouncementEmailResolutionTest` | Recipient with no linked `Profile.user_id` is skipped silently (no error); recipient with linked account but blank `email` is skipped silently; recipient with valid email is queued — mirrors `_resolve_result_notification_recipients`'s exact behavior. |
| `AnnouncementPublishTest` | Publishing calls `notify_many` with the deduplicated recipient set; `send_email=True` calls `queue_email` once per unique email; `Notification` rows exist afterward with `category="announcement"` and the correct `link`. |
| `AnnouncementIdempotencyTest` | Re-publishing an already-`PUBLISHED` announcement raises and queues nothing additional (mirrors `test_republish_rejected_and_results_unchanged`). |
| `AnnouncementAuthorizationTest` | `view_announcements` vs. `manage_announcements` enforcement; `broadcast_announcements` specifically required for `ALL`-audience publish (a user with only `manage_announcements` gets 403 on publish, 201 on create-as-draft). Revision 4 additions: the broadcast check is exercised through the `publish` action (after `get_object()`), not `get_permissions()`; a user holding only a system `staff` role with no announcement permissions granted gets 403 on create and publish, while an `owner` succeeds without any explicit grant. |
| `AnnouncementTenantIsolationTest` | Create in tenant A, assert tenant B's `tenant_context` sees zero rows — mirrors `ExamTenantIsolationTest`. |
| `AnnouncementTransactionRollbackTest` | Verifies `publish_announcement()` is atomic for its database writes. Simulates a failure *after* publication writes have begun inside the `transaction.atomic()` block (e.g. mock `queue_email` — or the last write step — to raise after `AnnouncementRecipient` and `Notification` rows have been created and at least one `EmailOutboxEvent` row written), then asserts that all of the following rolled back together: the announcement's `status` and `published_at` are unchanged (still pre-publish); zero `AnnouncementRecipient` rows exist for it; zero new `Notification` rows exist with its `link`; zero new `EmailOutboxEvent` rows exist from this attempt. Mirrors `test_failed_publication_creates_no_notification_events` in `examinations/tests.py`. **Distinct from `AnnouncementDeliveryFailureTest` below**, which tests the opposite case: a failure *after* a successful commit must not undo the committed publication. |
| `AnnouncementEmptyAudienceTest` | Added in Revision 4 (Option A). Publishing an announcement whose audience resolves to zero eligible recipients (e.g. a `SECTION` with no current students, or one whose students have no linked accounts) returns HTTP 400 with "No eligible recipients were found for this audience." Asserts the announcement's `status` and `published_at` are unchanged, and that zero `AnnouncementRecipient`, `Notification`, and `EmailOutboxEvent` rows exist for it afterward. |
| `AnnouncementDeliveryFailureTest` | Mock `notifications.tasks.send_mail` to simulate SMTP failure — confirms the already-committed publish/notification-queue state is unaffected (mirrors `test_failed_publication_creates_no_notification_events`'s *inverse* case: a failure *after* commit must not roll back anything, since it's now `send_outbox_email`'s problem, not `publish_announcement()`'s). |
| `AnnouncementMigrationTest` | `manage.py makemigrations --check --dry-run` clean after `0001_initial.py` is authored; reverse-then-forward round-trip, same discipline as the AcademicYear FK migrations. |
| `AnnouncementRecipientSnapshotTest` | New in this revision (issue #4): `mine/` reflects the persisted `AnnouncementRecipient` snapshot, not live audience membership — a student who was resolved at publish time still sees the announcement after their `StudentLevel` changes; a student added to the section *after* publish does not retroactively see it. `unique_together` DB constraint holds even if the resolver were (hypothetically) called with a duplicate `user_id`. |
| `AnnouncementCancelTest` | New in this revision (issue #5): `SCHEDULED → DRAFT` via `cancel/` clears `scheduled_at`; not available once `PUBLISHED`; `DRAFT` hard-delete succeeds, post-`DRAFT` delete only archives. |
| Phase 3 (scheduled publish) | `AnnouncementScheduledPublishTest` — Beat-triggered task publishes exactly the due announcements, enters the correct tenant schema explicitly, is idempotent against being invoked twice for the same announcement, **and (new in this revision) one tenant's simulated failure (mocked exception mid-loop) does not prevent a later tenant's due announcements from publishing** — directly testing the per-tenant `try`/`except` isolation specified in §Phase 2, which the cited precedent (`recover_stale_outbox_events`) does not itself have. |

**Acceptance criteria** (checklist form, mirroring `PHASE_1_3B_IMPLEMENTATION_PLAN.md`'s §13 style):
- [ ] `manage.py check` and `makemigrations --check --dry-run` clean.
- [ ] All tests in the table above pass.
- [ ] No endpoint accepts a client-supplied recipient list (confirmed by code review, not just test absence).
- [ ] `broadcast_announcements` permission is distinct from `manage_announcements` and enforced only on `ALL`-audience publish, inside the `publish` action after `get_object()` (confirmed by `AnnouncementAuthorizationTest`).
- [ ] The three permissions are seeded via `SYSTEM_PERMISSIONS` and the existing `post_migrate` signal, with no separate permission data migration; only the `owner` role holds them automatically, and other roles hold them only after an explicit grant through role management (confirmed by `AnnouncementAuthorizationTest`).
- [ ] Publishing to an audience with zero eligible recipients returns HTTP 400, leaves the announcement unpublished, and writes no `AnnouncementRecipient`, `Notification`, or `EmailOutboxEvent` rows (confirmed by `AnnouncementEmptyAudienceTest`).
- [ ] A user matching two audience rules receives exactly one in-app notification and at most one email (confirmed by `AnnouncementAudienceResolutionTest`, deduped by canonical `user_id`, not by `Profile` row).
- [ ] `publish_announcement()`'s database writes (status flip, `AnnouncementRecipient`, `Notification`, `EmailOutboxEvent` rows) roll back together on any failure (confirmed by `AnnouncementTransactionRollbackTest`); a simulated post-commit dispatch/delivery failure does NOT roll back any of them (confirmed by `AnnouncementDeliveryFailureTest`).
- [ ] The scheduled-publish task's per-tenant failure isolation is confirmed by test (one tenant's mocked failure does not block another tenant's due announcements).
- [ ] `mine/` reflects the persisted `AnnouncementRecipient` snapshot, confirmed to diverge correctly from live audience membership when membership changes after publish.
- [ ] Tenant isolation confirmed by test, not assumed.
- [ ] `AcademicYear` Stage B untouched (confirmed by `git status` showing no changes under `backend/academics/` or `PHASE_1_3B_*`).

**Deployment/rollback**: new app, new migration, no existing table altered — rollback is simply reversing `0001_initial.py` and removing `announcements` from `TENANT_APPS`, safe at any point before production data exists in the new table (same "safe only before later work depends on it" discipline as every other migration in this engagement).

## Lifecycle and Permission-Seeding Clarifications (resolves issue #5 — recommendations, still pending product-owner confirmation)

- **Can a `SCHEDULED` announcement be edited or cancelled?** Recommendation: **yes.** `SCHEDULED` is still pre-publish — no recipient has been resolved and no notification has been sent yet (that only happens at the moment `publish_announcement()` actually runs, whether triggered by the scheduled task or an immediate manual publish). The existing immutability rule ("`PUBLISHED` is a one-way gate") therefore does not need to apply to `SCHEDULED`. A dedicated `POST /api/announcements/{id}/cancel/` action (permission: `manage_announcements`) reverts `SCHEDULED → DRAFT` and clears `scheduled_at`; normal `PATCH` continues to work on `SCHEDULED` announcements exactly as it does on `DRAFT` ones.
- **Can a `DRAFT` be hard-deleted?** Recommendation: **yes, `DRAFT` only.** Before any recipient resolution or notification has occurred, there is nothing to preserve an audit trail for — a hard `DELETE` is safe. Once an announcement has ever left `DRAFT` (i.e. `SCHEDULED`, `PUBLISHED`, or `ARCHIVED`), `DELETE` instead performs the soft `→ ARCHIVED` transition described in §Phase 3, never a physical row delete, since `AnnouncementRecipient` rows may already reference it.
- **How are the three new permission codenames (`view_announcements`, `manage_announcements`, `broadcast_announcements`) provisioned for existing and newly-created tenants?** Resolved by Phase 0: through the existing `post_migrate` signal in `backend/roles/signals.py`, by appending three entries to `SYSTEM_PERMISSIONS` in `backend/roles/constants.py` during Phase 1. Existing tenants receive them on the next `migrate_schemas`; new tenants receive them at creation. Only the `owner` role is granted them automatically; other roles need them granted through `RoleViewSet`. No separate data migration. Full detail in §Phase 1, "How these permissions are provisioned".

## Remaining Unresolved Risks (flagged, not resolved here)

1. **Scheduled-publish Celery Beat task's exact interval** — proposed "mirror `recover-stale-outbox-events`'s 10-minute cadence" but not confirmed; a tighter interval may be wanted for time-sensitive announcements.
2. **Whether `audience_section`/`audience_level` should support multiple sections/levels at once** (e.g. "Sections 10-A and 10-B") — current design is single-section/single-level only for MVP; flagged as a Phase 4+ stretch item, not designed here.
3. **The pre-existing `Profile.user_id` non-uniqueness gap** (confirmed in this revision, §Audience Resolution) is a latent data-integrity question affecting more than just this feature — not something this plan resolves, but worth a separate, dedicated look outside this feature's scope.
4. **`recover_stale_outbox_events`'s own missing per-tenant failure isolation** (confirmed in this revision, §Scheduled Publish) is a pre-existing gap in unrelated code this plan does not fix, flagged only because this plan's own new task deliberately does not repeat it.

---

**Superseded:** this closing note originally said nothing was implemented. The backend is now implemented; see §17.

## 17. As Built (Revision 5)

### Files
- `backend/announcements/`: `models.py`, `services.py`, `tasks.py`, `serializers.py`, `views.py`, `urls.py`, `admin.py`, `migrations/0001_initial.py`, `tests.py`.
- `backend/config/settings.py`: `announcements` in `TENANT_APPS`; `publish-due-announcements` added to `CELERY_BEAT_SCHEDULE`.
- `backend/config/urls.py`: `api/announcements/`.
- `backend/roles/constants.py`: `view_announcements`, `manage_announcements`, `broadcast_announcements`.
- `backend/academics/views.py`: `ProtectedDeleteMixin` on the level and section viewsets, so a delete blocked by `on_delete=PROTECT` returns 400 instead of 500.

### Statuses and scheduling rules
- `draft` → `scheduled` (schedule) → `draft` (cancel); `draft` or `scheduled` → `published` (publish); `published` → `archived` (archive).
- A draft may have no scheduled time or a future one. A scheduled announcement must have a future time on every save; an overdue one must be rescheduled or cancelled. A published announcement may keep a past scheduled time.
- `Announcement.save()` runs `full_clean()`. `QuerySet.update()`/`bulk_create()` bypass it, so app code must not use them for `Announcement` writes.
- Stored values are lowercase (`"scheduled"`); use `Announcement.Status.*` / `Announcement.AudienceType.*` in code.

### Publishing (`services.publish_announcement`)
- Locks the announcement row (`select_for_update`), so concurrent publishers (a user and the task, or two workers) serialise; the second is rejected as already published.
- Resolves recipients first. Empty audience → 400 "No eligible recipients were found for this audience.", nothing written, announcement unchanged.
- Recipients: scalar `Profile.user_id` values collected into one set across all audience rules, then one batched `accounts.User` query (`is_active=True`). Ids with no active account are dropped. A blank email keeps the in-app recipient but skips email.
- Audiences: `section`/`level`/`all_students` = active students with a current enrollment; `all_parents` = parents of active students; `all_staff` = active `StaffMember`s; `all` = the union. Section and level audiences do not include parents.
- In one transaction: status and `published_at`, `AnnouncementRecipient` rows, one `notify_many()` call, and one `queue_email()` per unique email when `send_email` is set. Any failure rolls all of these back. Email dispatch happens after commit; a broker failure then leaves the outbox row `PENDING` for `recover_stale_outbox_events` and does not undo the publication.

### API (`/api/announcements/`)
| Endpoint | Permission | Notes |
|---|---|---|
| `GET /` | `view_announcements` | Paginated (`StandardResultsPagination`); `?status=`, `?audience_type=`, `?search=`, `?ordering=`; default newest first. |
| `POST /` | `manage_announcements` | Creates a draft; `status`, `created_by_user_id`, `published_at` are read-only. |
| `GET /{id}/` | `view_announcements` | Includes `recipient_count`. |
| `PATCH`/`PUT /{id}/` | `manage_announcements` | Draft or scheduled only (row-locked); otherwise 400. |
| `DELETE /{id}/` | `manage_announcements` | Draft: hard delete. Published: archive. Scheduled: 400, cancel first. Archived: 400. |
| `POST /{id}/schedule/` | `manage_announcements` | Body `{"scheduled_at": ...}`, must be in the future. |
| `POST /{id}/cancel/` | `manage_announcements` | Scheduled → draft. |
| `POST /{id}/publish/` | `manage_announcements`, plus `broadcast_announcements` when audience is `all` | Broadcast check runs after loading the object. |
| `POST /{id}/archive/` | `manage_announcements` | Published → archived. |
| `GET /{id}/recipients/` | `manage_announcements` | Paginated `user_id`, `email_sent`, `created_at`; no email addresses. |
| `GET /mine/` | Authenticated only | Published announcements from the caller's recipient snapshot: `id`, `title`, `body`, `published_at`. 404 on the public domain. |

Errors use the project shape `{"non_field_errors": [...]}` or field keys. Another school's ids return 404, since every query runs in the request's tenant schema.

### Scheduled publishing
- `announcements.tasks.publish_due_announcements`, every 5 minutes via Celery Beat. It iterates active organizations (`is_active=True`, excluding `public`), enters each schema with `schema_context`, and publishes up to 100 due announcements per tenant per run, oldest first.
- One failing tenant is logged and skipped; others continue. An announcement that fails is left `scheduled` and retried next run. One already published elsewhere is skipped. One with an empty audience is returned to `draft` with its time cleared and a warning logged, so it stops failing every run.
- Requires a running Beat process; the existing rule of exactly one Beat instance applies.

### Test results (isolated test database `test_edusekai_db` only)
- `manage.py test announcements academics notifications roles --keepdb`: **145 tests, OK**, 9361.7 s, exit 0.
- `manage.py check`: no issues. `makemigrations --check --dry-run`: no changes. `git diff --check` on changed tracked files: clean.
- Announcements alone: 36 tests covering validation, recipient resolution (each audience, dedup, missing accounts, blank emails), publishing, rollback at each write boundary, post-commit dispatch failure, lifecycle transitions, the scheduled task (due, future, draft, empty, retry, lost race, failing tenant), API permissions, broadcast enforcement, `/mine/`, cross-tenant 404s, and the academics delete 400.

### Deployment (not yet done; requires separate approval)
1. Back up the database.
2. `python manage.py migrate_schemas` creates both announcement tables in every tenant schema and, through the existing `post_migrate` signal, seeds the three permissions. Only `owner` receives them automatically.
3. Grant `view_announcements` / `manage_announcements` / `broadcast_announcements` to other roles through role management.
4. Restart the Celery worker and the single Beat process so the new task and schedule load.
5. Rollback: revert the code, then `python manage.py migrate_schemas announcements zero` only while no real announcement data needs keeping.

### Known limitations
- No frontend screens.
- Concurrency protection is a row lock. It is exercised by sequential repeat-publish and simulated lost-race tests, not by a true parallel multi-worker test.
- The 5-minute interval is a chosen default, not a confirmed product requirement.
- `recover_stale_outbox_events` still lacks per-tenant failure isolation (unchanged, out of scope).
- `Profile.user_id` is not unique; recipients are deduplicated by account, but the underlying data gap is not fixed.
- The full regression run is slow (about 2.6 hours for 145 tests) because most tests build their own tenant schema.
