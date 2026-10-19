# Phase 6 - Owner Decisions and Readiness Gate

No implementation was changed in this phase. Everything below is either **verified** (command/query/test run in this
phase, evidence stated), a **recommendation**, or an **assumption** (marked as such). No decision was taken on the
owner's behalf; none of the options below is implemented unless it says so.

## 1. Current implementation state (verified)

- Branch `main`; `git status --short` = 200 entries. The 5 above the earlier 195 are exactly the remediation edits:
  `backend/staff/views.py`, `backend/students/views.py`, `tenant_frontend/src/hooks/useStaff.ts`,
  `tenant_frontend/src/hooks/useStudents.ts`, and `PHASE_6_RISK_REMEDIATION_REPORT.md`. No file was changed in this phase except this document.
- Dev database `edusekai_db` (read-only queries only): certificates migration at `0001_initial`; no `certificates_idcardtoken`
  table; **0 certificates in every tenant** (so 0 legacy-format seals); the six permissions are held by `owner` only in all 4 tenants.
- Migration `0002` is generated and **not applied** to any persistent database (re-verified by query at the end).
- Flag defaults (`config/settings.py`): `CERTIFICATE_ACCEPT_LEGACY_SEALS = True`, `ID_CARD_ACCEPT_LEGACY_TOKENS = True`.
  Neither is set in `.env`, so both are on everywhere unless an environment sets them to `False`.

## 2. Test evidence (exact commands, run in this remediation cycle)

All commands run from `backend/` with `./.venv/Scripts/python.exe`, against the isolated `test_edusekai_db` (`--keepdb`).

| Command | Exit | Result |
|---|---|---|
| `manage.py test certificates --keepdb` | 0 | **36 tests, OK**, 0 failures, 0 errors, 0 skips (3306.5 s) |
| `manage.py test staff --keepdb` | 0 | **13 tests, OK** (302.8 s) |
| `manage.py test students --keepdb` | see section 11 | see section 11 |
| `manage.py check` | 0 | no issues |
| `manage.py makemigrations --check --dry-run` | 0 | no changes detected |
| `npx tsc --noEmit` (tenant_frontend) | 0 | no errors |
| `npx eslint` on all certificate frontend files | 0 | clean (the `any` errors in `useStaff.ts`/`useStudents.ts` are pre-existing; I added none) |
| `npm run build` | 0 | compiled; certificate, id-card and verify routes listed |

Checklist coverage (test names in `certificates/tests.py` and `tests_remediation.py`):

| Required coverage | Tests |
|---|---|
| TC valid and invalid lifecycle histories | `test_valid_records_and_every_refusal` (withdrawn record, transferred record, active, inactive without record, legacy without record, record of another student, record/status mismatch, non-exit record, duplicate), `test_unauthorized_issuer_and_no_side_effects`, `test_cancel_and_reissue_keep_history_and_still_need_the_record`, `test_lifecycle_records_of_another_tenant_cannot_be_used`, `test_concurrent_duplicate_tc_issues_exactly_one` |
| Experience: active staff, missing joining date, invalid dates | `ExperienceCertificateRulesTest.test_rules`, `.test_authorization_and_tenant_isolation` |
| QR tokens: uniqueness, revocation, malformed, tenant isolation, legacy | `OpaqueIdCardTokenTest` (4 tests) incl. `test_legacy_signed_tokens_are_accepted_only_while_the_setting_is_on` |
| HMAC: current key, legacy seals, unknown key id, invalid signature, missing key, fail-closed | `IntegrityKeyVersioningTest` (7 tests) + `test_issuing_fails_closed_when_no_integrity_key_is_configured` |
| Backend JSON/PDF authorization | `test_certificate_fields_are_limited_by_permission`, `test_authorization_tenant_isolation_settings_and_audit` (viewer 200 on PDF, ID-card holder 403, tenant 404) |
| Picker search/pagination/tenant/permissions | `test_student_and_staff_picker_search_pagination_permissions_and_isolation` |

**Gaps stated honestly:** (a) the picker UI, rotate button and new certificate form have no automated frontend test (no
framework in the repo); they are covered by tsc/eslint/build only. (b) Legacy-seal and legacy-token behavior is tested with
settings overrides and in-memory/test-DB records, not on a database that held real legacy rows (none exist in dev).
(c) I did not re-run attendance/academics/announcements; nothing they depend on changed.

## 3. Decision A - legacy Transfer Certificates

**Verified behavior:** TC needs `approve_certificates`, status transferred/withdrawn, **and** a matching `PromotionRecord`
(newest transferred/withdrawn record whose action equals the status). In the earlier dev-data copy all 13 students with those
statuses had no such record, so every one of them is refused. Issuing never changes status/enrollment/history.

| | Option A - strict (current) | Option B - audited exception (NOT implemented) |
|---|---|---|
| What | Keep the rule. | New permission `override_transfer_exit_check`; justification required (min length), stored on the certificate and in the audit log (`certificate_issued_with_override`); one live TC per student still enforced by the existing index. |
| Operational effect | Legacy leavers cannot get a TC at all until their exit is in the workflow. The workflow only accepts **active students with a current enrollment**, so a student who has already left cannot be re-recorded without first re-activating them, which this project forbids doing just to print a document. **Practically: legacy cases are stuck.** | A named role (proposed: principal) can issue for legacy leavers with a recorded reason; weaker guarantee, but auditable and visible on the staff detail. |
| Risk | Parents of legacy leavers cannot be served; pressure to edit statuses in admin. | Override could be used routinely; mitigated by permission scope + audit review. |

**Recommendation: Option A for new exits, plus Option B limited to principal-level, only if the owner confirms that legacy
leavers exist who need TCs.** Required from the owner: choose A or A+B and name the role.
Tests to add if B is chosen: override permission required, justification required, audit row written, duplicate still blocked,
tenant isolation, override flag shown to staff only (not on public verification).

## 4. Decision B - staff employment dates

**Verified:** `StaffMember` has `joining_date` (optional) and `is_active`; no exit/relieving date exists anywhere. Current rule:
active staff blocked; joining date required and used as start; issuer enters end date (not future, not before start), stored as
`end_date_source: issuer_entered` in the snapshot and in the audit log.

| | Option A - keep labelled issuer-entered date (current) | Option B - authoritative `exit_date` (NOT implemented) |
|---|---|---|
| What | Nothing more. | Nullable `StaffMember.exit_date` (+ optional `exit_reason`), set by a deactivation action that requires the date. |
| Effect | Works today; the date is a claim by the issuer, not verified. | Experience certificates require a recorded exit date; unrecorded former staff must be completed first. |
| Affected workflows | none | staff update/deactivation (`StaffMemberUpdateSerializer` and Django admin both change `is_active` today), leave (`staff/leave_services.py` rejects inactive staff), attendance/timetable pickers that filter on `is_active`, the experience-certificate service. |
| Backfill | n/a | **Never infer from `is_active`.** Add nullable column, leave NULL, owner enters dates per former employee (or accepts "date not recorded -> cannot certify"). |
| Migration | none | `staff/0003` nullable columns only; additive; safe to roll back before data is entered; reverse after entry drops the column (back up first). Not created. |

**Recommendation: Option A now (documented, labelled), schedule Option B before any school relies on experience certificates
at scale.** "Employed to date" wording for **current** staff: **not approved, not implemented** - owner must say yes/no and
approve the exact sentence.

## 5. Decision C - retiring legacy QR tokens and legacy certificate seals

These are **two independent decisions**:

| | Legacy ID-card QR format | Legacy certificate seal (and old key ids) |
|---|---|---|
| What it is | A printed code signed with Django `SECRET_KEY`, embedding record UUID + schema name. | A stored digest on the certificate row (bare 64-hex = made with `SECRET_KEY`; `k<id>:` = made with a configured key). |
| Who holds it | Cardholders (paper/plastic out in the world). | Your own database rows. |
| If you switch it off | The old card's QR answers "invalid" (same as unknown). The card itself is fine; reprint fixes it. Reversible by re-enabling the flag. | The certificate row **fails verification** ("could not be verified") although it is genuine. Fixing needs the old key back and a re-seal. |
| Prerequisite | Cards reprinted. | Every row re-sealed under the active key (no bulk re-seal command exists yet; re-seal happens only on status change). |
| Flag | `ID_CARD_ACCEPT_LEGACY_TOKENS` | `CERTIFICATE_ACCEPT_LEGACY_SEALS` (bare digests) and the key list (`k<id>:` seals) |

**Retirement plan (nothing executed):**
1. *Identify without exposing secrets.* Seals: per tenant, `select left(integrity_hash, strpos(integrity_hash,':')) as key_id, count(*) ... group by 1`; bare digests = `integrity_hash not like 'k%'`. Verified now: dev has 0 certificates, so 0 legacy seals. ID cards: legacy tokens were never stored, so they **cannot be counted from the database**; the only sources are the owner's print records. (Optional, needs approval: count legacy-format verifications in the audit log to see whether old cards are still scanned.)
2. *Were legacy cards printed?* Owner to answer. Assumption: none outside dev/testing, because the ID-card feature was built in this project cycle; unverified.
3. *Reprint/communication window:* owner sets (suggested: one term). Reprinting uses the existing "replace QR code" action, which issues an opaque token.
4. *Retirement date:* owner sets; then set `ID_CARD_ACCEPT_LEGACY_TOKENS=False` in that environment.
5. *New cards opaque only:* verified by `test_token_is_random_stable_unique_and_reveals_nothing` (no `:` in tokens, 32-char random) - new cards never use the legacy format regardless of the flag.
6. *Certificates verify while their key is configured:* verified by `test_rotation_keeps_old_certificates_verifiable_until_the_key_is_retired`; retired key => fails closed.
7. *Behavior with legacy acceptance off:* verified in isolation by `test_legacy_signed_tokens_are_accepted_only_while_the_setting_is_on` and `test_legacy_unversioned_seals_only_while_accepted_and_never_for_new_seals`.
Seal-key retirement additionally needs: a bulk re-seal command (proposed, not built), then the per-tenant key-id count at zero.
**Environment note (verified in code):** in local `DEBUG` the seal key id is `dev`; those seals never verify when `DEBUG=False`. Dev data must not be carried into staging.

## 6. Decision D - certificate PDF privacy

**Verified:** `GET /api/certificates/<id>/pdf/` requires only `view_certificates`; it writes a `certificate_downloaded` audit row (actor, object id, no content). The PDF carries holder name, admission/employee number, class, dates, reason, conduct and - **only on a Transfer Certificate** - the student's date of birth (asserted present for TC and absent for bonafide by `test_pdf_content_qr_payload_and_missing_branding`). It never prints internal notes, user ids or the snapshot JSON.

| | Option A - viewers may download (current) | Option B - restrict to issuers/approvers/cancellers (NOT implemented) |
|---|---|---|
| Effect | Auditors/read-only staff can re-download any issued document incl. TC date of birth. | Only `issue_`/`approve_`/`cancel_certificates` holders download; read-only users see status/number only. |
| Registrars | No change. | No change **if** registrars hold `issue_certificates`; a pure `view_certificates` role loses downloads. |
| Change size | none | Small (reuse the existing sensitive-permission tuple in `download_pdf`) + test; no new permission. |

**Recommendation: Option B** (least privilege; the document is the sensitive artefact). Needs owner approval before changing.

## 7. Decision E - the six permissions (final matrix)

Seeded today: **owner only**, all four tenants (verified by query). `override_transfer_exit_check` is **proposed, not created**.

| Permission | API operations | UI | Also needs | Recommended holder | Tests |
|---|---|---|---|---|---|
| `view_certificates` | list, detail (basic fields), PDF, settings GET | Certificates page, sidebar entry | - | Registrar/office staff, principal | `test_authorization_tenant_isolation_settings_and_audit`, `test_certificate_fields_are_limited_by_permission` |
| `issue_certificates` | create bonafide/character; reissue them; full detail view | Issue form (those two types) | `view_certificates` to see the list; `view_student` for the picker | Registrar/office staff | same + `test_unauthorized_issuer_and_no_side_effects` |
| `approve_certificates` | create transfer/experience; reissue them; full detail | Issue form (those two types) | `view_certificates`; `view_student` / `view_staff` | Principal / tenant admin only | `ExperienceCertificateRulesTest`, `TransferLifecycleTest` |
| `cancel_certificates` | cancel any type; reissue (together with the type's issue/approve permission); full detail | Cancel / Reissue buttons | `view_certificates`; reissue also needs the type permission | Principal / tenant admin only | lifecycle tests |
| `manage_certificate_settings` | settings PATCH (signatory, signature image) | Settings card | `view_certificates` (the card sits on the certificates page) | Tenant admin only | settings assertions |
| `generate_id_cards` | ID-card data, PDF, replace QR | ID Cards page, Print, Replace QR | **`view_student` and/or `view_staff`** - the picker calls those lists | Office/admin staff | `test_id_cards_minimal_data_and_public_verification`, `OpaqueIdCardTokenTest` |
| `override_transfer_exit_check` | **proposed only** | - | `approve_certificates` | Principal, if Decision A-B is chosen | none (not built) |

Findings from building this matrix: (1) a role with `generate_id_cards` but no `view_student`/`view_staff` can open the ID-card page but cannot pick anyone (the lists return 403) - grant them together; (2) `cancel_certificates` can cancel a TC without `approve_certificates` (cancelling is not issuing) - keep both with the same role unless the owner wants cancellation separated. No permission or role assignment was changed.

## 8. Decision F - non-Latin fonts

**Verified by running the guard on sample text (this phase's earlier probe; PDFs rendered and inspected as images earlier):**

| Script | PDF result |
|---|---|
| Basic Latin; Latin-1 accents (e.g. Jose, Muller, Francois-type letters); curly quote and en dash | Rendered and accepted |
| Latin Extended-A samples (e.g. Polish/Czech letters), Vietnamese, Greek, Cyrillic, Devanagari (Nepali/Hindi) incl. Devanagari digits, Arabic, Bengali, Tamil, CJK | **Rejected** with a message naming the characters |

Forcing Devanagari through the renderer produced empty boxes, which is why the guard exists. The guard runs at certificate issue time and when an ID-card PDF is requested (tests: `test_type_validation_...` Devanagari case, `test_id_card_pdf_refuses_text_the_font_cannot_print_...`). The **on-screen React print card is different**: it uses the browser's fonts, so it may display scripts the PDF rejects; **I did not render it, so I make no claim about it.**

To add a font (needs your approval; nothing added): a TTF whose licence permits embedding (e.g. an SIL OFL face - the owner must verify the licence text), registered in `certificates/pdf.py`, glyph coverage tested per script. **Important unverified caveat:** Devanagari, Arabic, Bengali and Tamil need *text shaping* (conjuncts, vowel-sign reordering, joining); I have not verified that ReportLab shapes them, and plain glyph-by-glyph drawing would look wrong even with a correct font. Expect either an extra shaping dependency or Latin-only PDFs. Impact (estimates, unmeasured): subsetting keeps PDFs modest; wrapping and the QR/layout tests need per-script cases.

## 9. Migration `0002` - forward and reverse (rehearsed on a disposable copy)

Method: `pg_dump` of `edusekai_db` (read-only) restored into `rehearsal_p6b_edusekai`; the target database name was asserted before every write; the copy and the dump were deleted afterwards; the dev DB was re-queried and is unchanged (still `0001`, no token table).

**Forward (exact SQL, per tenant schema):** widen `certificate.integrity_hash` `varchar(64)` -> `varchar(128)` (metadata-only in PostgreSQL, no rewrite); create `certificates_idcardtoken` with `token varchar(64) UNIQUE`, check constraint `idcard_exactly_one_subject`, two FKs, partial unique indexes `idcard_one_live_token_per_student` / `..._per_staff` (`WHERE revoked_at IS NULL`), plus the usual lookup indexes. Matches the models (confirmed against the SQL). Applied to 4 tenants + public in the copy: exit 0, 1 migration row each. Widening accommodates versioned seals (`k<id>:` + 64 hex = 67+ chars).

**Reverse (exact SQL):** `DROP TABLE certificates_idcardtoken CASCADE;` then `ALTER COLUMN integrity_hash TYPE varchar(64);`
- *Case A - a versioned seal exists:* **fails** (`StringDataRightTruncation: value too long for varchar(64)`). Because PostgreSQL DDL is transactional, the whole reverse rolled back: the certificate, both tokens and the migration record were intact afterwards (verified). Good fail-safe, but it blocks rollback.
- *Case B - no versioned seal left, tokens exist:* **succeeds silently and destroys every ID-card token** (2 rows -> table gone; after re-applying forward the table is empty). Every printed opaque QR would then answer "invalid" until cards are replaced, and revocation history is lost. Verified.

**Recommendation:** after the first certificate or card is issued on a real database, **do not use the reverse migration**. Use a forward fix, or restore from a backup taken immediately before the deploy. A small code guard (refuse to reverse while tokens exist) is possible but would modify a generated migration; **not done**, owner/reviewer to decide. Production procedure when authorized: backup -> `migrate_schemas --shared` -> `migrate_schemas --tenant` -> verify counts. Legacy QR tokens are unaffected by the migration (they were never stored); they verify only while `ID_CARD_ACCEPT_LEGACY_TOKENS=True`.

## 10. Outstanding blockers and limitations

1. Owner answers needed: A (strict vs audited exception + role), B (keep labelled date vs `exit_date`; "to date" wording yes/no), C (were legacy cards printed; windows/dates), D (PDF access), E (role assignments), F (fonts).
2. No frontend tests; PDF not checked on a physical printer; React on-screen card not rendered.
3. No bulk re-seal command, so certificate-key retirement is not yet possible.
4. Migration `0002` unapplied; reverse is unsafe after issuance (section 9).
5. Dev-sealed (`kdev`) records must not move to other environments.

## 11. Readiness classification

**Ready for development-branch merge. Blocked pending owner decisions for staging/rollout** - specifically A, B and E (they change who can issue and what is certified), plus the forward-only migration policy in section 9. Decisions C, D and F do not block a staging trial: C because both compatibility flags default to the safe (accepting) value, D because no new exposure exists beyond what the previous report disclosed, F because unsupported text fails clearly. This classification rests on the tests above and on the rehearsal; it is **not** a claim of production readiness.

### students regression result
(appended below when the run completed)

---

## 12. Status update, 2026-10-19: the `students` regression run did not complete

**This section supersedes the readiness wording in section 11 and the placeholder under "students regression result" above.**

### What happened (verified by inspection on 2026-10-19 12:36)
- The original run was `manage.py test students --keepdb` (run from `backend/` with `./.venv/Scripts/python.exe`, isolated test DB `test_edusekai_db`), started 2026-10-17 20:28:50 as PIDs 6548 / 20596.
- It is **no longer running**. No `manage.py test` process exists and no Python process of any kind is running, which is consistent with the machine or session having been restarted.
- Its log (`remed_reg_students.txt` in the session temp directory) was last written 2026-10-17 21:05:44, at tenant-schema setup number 121, **mid-run**. It contains **no `Ran N tests` line and no `OK`/`FAILED` line**.
- No exit code was recorded: the wrapper that wrote `students exit=<code>` was killed with the process; the exit file contains only `staff exit=0`.
- **Conclusion: the outcome of that run cannot be recovered.** No pass, fail, error or skip count exists for it. Partial progress and the absence of visible errors are not evidence of a pass.

### State left behind (read-only queries, nothing changed)
| Item | Finding |
|---|---|
| Dev DB `edusekai_db` | Unchanged: certificates migration still `0001_initial`, no `certificates_idcardtoken` table, 4 tenant schemas as before. |
| Disposable rehearsal databases | None present (`edusekai_db` and `test_edusekai_db` only). |
| Test DB `test_edusekai_db` | **A stale tenant schema `promo_test_school` was left by the killed run** (a students test's schema). No other connections are open. |
| Git | 201 status entries, identical to the previous report; this section is the only edit made in this task. |

### Consequence for a rerun (not performed)
A `--keepdb` rerun will very likely collide with the stale `promo_test_school` schema when that test creates its tenant, the same failure mode that happened once before after an interrupted run. Clearing it means dropping that schema (and its row in the test DB's organization table) **inside `test_edusekai_db` only**, with the connected database name asserted first. I have **not** done this and have **not** started a rerun, because it modifies a persistent database and you asked me to report the limitation first.

Options for the owner: (a) approve the stale-schema cleanup in `test_edusekai_db` followed by a single fresh `manage.py test students --keepdb` (about 30 to 40 minutes, based on the earlier full run of 1817 s); (b) accept the earlier independent `students` result (85 tests, OK, 1817 s, from the pre-Phase-6-remediation run recorded in the validation report) for the unchanged parts and rerun only the students tests that exercise the changed list view; or (c) defer.
Why a rerun is warranted at all: the remediation changed `backend/students/views.py` (added `search` and `status` filtering to `StudentListView`), so the earlier 85-test pass does not cover the current code.

### Verification table (status as of 2026-10-19)

| Check / suite | Command | Result | Exit | Status |
|---|---|---|---|---|
| Certificates | `manage.py test certificates --keepdb` | 36 tests OK | 0 | Newly verified in the remediation run (log read: `Ran 36 tests in 3306.524s`, `OK`) |
| Staff | `manage.py test staff --keepdb` | 13 tests OK | 0 | Newly verified (`Ran 13 tests in 302.787s`, `OK`; exit file `staff exit=0`) |
| **Students** | `manage.py test students --keepdb` | **no result: run killed at schema 121, no summary** | **not recorded** | **Unverified for the current code** |
| Students (earlier, before remediation edits) | same | 85 tests OK in 1817.3 s | 0 | Previously reported; does not cover the changed `StudentListView` |
| Django check | `manage.py check` | no issues | 0 | Reported in the previous cycle; not re-run in this task |
| Migration drift | `manage.py makemigrations --check --dry-run` | no changes | 0 | Reported; not re-run in this task |
| TypeScript | `npx tsc --noEmit` | no errors | 0 | Reported; not re-run in this task |
| ESLint (certificate files) | `npx eslint <files>` | clean | 0 | Reported; not re-run in this task |
| Frontend build | `npm run build` | compiled | 0 | Reported; not re-run in this task |
| Migration 0002 rehearsal | disposable DB copy | forward SQL matches models; reverse fails safely with a versioned seal, silently deletes tokens without one | n/a | Reported and preserved; the copy and dump were removed; dev DB re-confirmed unchanged today |

"Reported; not re-run in this task" means I did not repeat them today and am relying on the previous cycle's evidence for those rows.

### Readiness classification (replaces section 11)
**Development verification incomplete.** Reason: the students regression suite, which is affected by the remediation change to `students/views.py`, has no completed result. All other automated checks above were reported passing. When the students suite completes and passes, the classification would move to **Development verification passed** (owner decisions A to F, the forward-only migration policy and staging validation remain outstanding either way). It is not production-ready.

---

## 13. Test-database cleanup scope and an unexplained dev-database migration (recorded 2026-10-19)

**Sections 1, 9 and 12 above state that the dev database is at migration `0001` with no token table. That was true when written and is no longer true; see 13.2. This section supersedes those statements.**

### 13.1 Cleanup performed in `test_edusekai_db` (authorization applies to the first item only)

| # | Action | Authorized as written? | Evidence |
|---|---|---|---|
| 1 | `DROP SCHEMA "promo_test_school" CASCADE` in `test_edusekai_db` | **Yes** | Live connection asserted as `test_edusekai_db` (from `current_database()`, not from `.env`/settings, which name `edusekai_db`); 0 other connections; schema owned by `edusekai_user`; 70 tables, 327 indexes, 12 sequences; no foreign keys or views from other schemas pointing in or out. `CASCADE` was needed because the schema was non-empty and was limited to that schema by the dependency check. |
| 2 | `DELETE` of the one matching row (`schema_name='promo_test_school'`) from `public.organizations_organization` in the same transaction | **No: this was an additional action**, not named in the authorization. | Done because the students tests create a tenant with that unique schema name, so a stale organization row would have broken the rerun. The row's id was checked against the preflight; no `organizations_domain` row pointed at it; exactly 1 row was deleted. |

After the cleanup the test DB contained only `public` and 0 organization rows. The development database was not touched by either action.

### 13.2 Certificates migration `0002` found applied in the DEV database (unexplained)

**Facts (read-only queries, 2026-10-19):**
- `0002_alter_certificate_integrity_hash_idcardtoken` is recorded in `public` and all four tenants (`greenvalley_demo`, `spsghy`, `sunrisevalley_school`, `test_chk`) of `edusekai_db`.
- Applied at 07:07:58.5 UTC (`public`), then 07:08:01.5, 07:08:04.3, 07:08:06.7, 07:08:08.9 UTC for the tenants, i.e. 12:37:58 to 12:38:08 IST. The role-seeding that runs after each schema migration updated `roles_role.updated_at` at 07:08:02.8, :05.6, :07.7 and :10.0 UTC. The order (shared schema first, then each tenant in turn, with post-migrate seeding after each) is the signature of `migrate_schemas`.
- `0002` is the **only** migration applied in that window (no other app changed). The new tables exist and are empty: `certificates_certificate` 0, `certificates_idcardtoken` 0, `certificates_certificatesettings` 0 in every tenant.
- At 07:06:28 UTC my own read-only probe still reported `0001_initial`, so the application happened afterwards. No connection to the dev database was open at 07:10:54.

**What I did and did not do:** I did not run the migration. My transcript for the period lists no `migrate`/`migrate_schemas` command; every command of mine in the window ran only SELECT statements, wrote a markdown file, or listed processes. My calls at 07:06:58 and 07:09:15 UTC bracket a 2 min 17 s gap with no calls from me, and the migration falls inside it. This is evidence from my own log, not proof about other actors.

**Sources checked, and what each showed:**

| Source | Result |
|---|---|
| Dev DB `django_migrations` / `roles_role.updated_at` | Gives exact times and the `migrate_schemas` pattern; cannot name the actor. |
| PostgreSQL server log | Records no statements (`log_statement` is not set) and has no entry in 12:35 to 12:42 beyond an autovacuum notice and a checkpoint. No evidence. |
| PowerShell `ConsoleHost_history.txt` (no timestamps; last written 12:36:55) | No `migrate_schemas`; contains plain `python manage.py migrate` lines of unknown date and `cmd` entries. Commands typed inside a `cmd` window are not recorded there. Inconclusive. |
| Processes started that morning | Both frontend dev servers (`next dev`) started 12:37:09 to 12:37:26, 30 to 50 s before the migration; `codex.exe` and other editor processes started 12:33 to 12:35. `next dev` does not migrate. No backend dev server or Python process was running afterwards. A clue only; no causal evidence. |
| Repo launchers (`.bat`/`.cmd`/`.ps1`/VS Code tasks) | None that migrates or starts servers. `backend/entrypoint.sh` migrates on container start, but the Docker daemon is not running, so this path is ruled out for now. |
| Codex session logs | No sessions folder; its log database contains no migrate command text. No evidence, and this checks only the tool's local logs. |

**Conclusion: the cause is not determined.** The most consistent explanation is a person or tool running `migrate_schemas` in a terminal whose history is not recorded (for example a `cmd` window), at about 12:37:58 IST. That is a hypothesis, not a finding.

**Implications (assessed, not acted on):**
- The `0001` to `0002` step on the dev DB is exactly the forward step rehearsed on a disposable copy, so the schema should match the models. It succeeded in every schema.
- The tables are empty today, so nothing has been lost. That does **not** make a reverse safe in every respect: reverse also drops the token table, and the rehearsal showed it succeeds silently and destroys tokens if any exist, so the empty state can change at any time. It also would not undo whoever or whatever applied it.
- Whether any `kdev` seals or tokens are created from here depends on who uses the dev app next.

**Decisions taken in this task:** none on the database. I made **no** change to the dev database, did **not** reverse `0002`, did not alter any flag or key, and did not run any migration anywhere.
**Open (owner):** identify the actor if it matters (their own terminal, an IDE run configuration, another assistant, a scheduled task); decide whether the dev DB stays at `0002` (recommended: yes, because it is the intended state and reversing is the riskier operation) and whether to adopt a rule that migrations on the dev DB are applied only on request.

### 13.3 Status of the students regression run at the time of writing
The single authorized run (`manage.py test students --keepdb`, started 2026-10-19 12:41:16, log with its own exit-code line) is still in progress: 85 tests found, existing test DB in use, 44 tenant-schema setups completed by 12:52:58. **No result yet.** Readiness remains **Development verification incomplete**.

---

## 14. Verified `students` regression result and updated readiness (2026-10-19)

**This section completes 12 and 13.3 and replaces the readiness classification in sections 11 and 12.**

### 14.1 The run (newly verified, from the run's own log)
| Item | Value |
|---|---|
| Command | `./.venv/Scripts/python.exe manage.py test students --keepdb` (from `backend/`) |
| Database | Existing isolated test database (`Using existing test database for alias 'default'`); the live connection had been confirmed as `test_edusekai_db` before the cleanup that preceded the run |
| Start / end | 2026-10-19 12:41:16 to 13:09:24 (wall clock), 28 min 8 s |
| Test summary | `Ran 85 tests in 1680.555s` then `OK` |
| Failures / errors / skips | 0 / 0 / 0 (the summary line is plain `OK`, with no `skipped=` annotation; 0 `Traceback` lines in the log) |
| Real process exit code | **0** (`PROCESS_EXIT_CODE=0`, written by the same wrapper that ran the command; this is the test process's code, not the wrapper's) |
| Warnings / environment notes | None in the log. 172 tenant schemas were created and removed by the tests, as in the earlier full run. One run only; no duplicate, no interruption. |
| Log | `students_final_run.log` in the session scratchpad |

### 14.2 What this does and does not cover
- It covers the **current** `backend/students/views.py` (including the added `search` and `status` filtering on `StudentListView`) **for existing behavior**: 85 existing students tests, including list pagination, ordering and cross-tenant isolation, still pass.
- **None of the 85 students tests send the new `search` or `status` query parameters** (checked by searching `students/tests.py`). The new filters are covered only by the certificates test `test_student_and_staff_picker_search_pagination_permissions_and_isolation`, which passed in the 36-test certificates run. If the owner wants the filters covered inside the students app, a test there should be added; none was added in this task.

### 14.3 State after the run (read-only checks)
| Item | Finding |
|---|---|
| Test DB `test_edusekai_db` | No tenant schemas left (`public` only); 0 other connections. |
| Dev DB `edusekai_db` | Unchanged by this task. Certificates migration is at `0002` in `public` and all four tenants (see 13.2); `certificates_certificate`, `certificates_idcardtoken`, `certificates_certificatesettings`: 0 rows in each tenant; 0 other connections. **The unexplained application of `0002` remains unresolved.** |
| Git | 201 status entries; unchanged by the run and by this edit. |

### 14.4 Consolidated verification table

| Check / suite | Command | Result | Exit | Status |
|---|---|---|---|---|
| **Students (current code)** | `manage.py test students --keepdb` | **85 tests, OK, 0 fail/error/skip, 1680.555 s** | **0** | **Newly verified today** |
| Certificates | `manage.py test certificates --keepdb` | 36 tests OK (3306.524 s) | 0 | Verified in the remediation run (log read); not re-run today |
| Staff | `manage.py test staff --keepdb` | 13 tests OK (302.787 s) | 0 | Verified in the remediation run; not re-run today |
| Django check | `manage.py check` | no issues | 0 | Reported earlier; not re-run today |
| Migration drift | `manage.py makemigrations --check --dry-run` | no changes | 0 | Reported earlier; not re-run today |
| TypeScript | `npx tsc --noEmit` | no errors | 0 | Reported earlier; not re-run today |
| ESLint (certificate files) | `npx eslint <files>` | clean | 0 | Reported earlier; not re-run today |
| Frontend build | `npm run build` | compiled | 0 | Reported earlier; not re-run today |
| Migration `0002` rehearsal | disposable DB copy | forward SQL matches models; reverse fails safely with a versioned seal, silently deletes tokens without one | n/a | Reported earlier and preserved; copies removed |

Not run at all: automated frontend tests (none exist), physical-printer checks, rendering of the on-screen React ID card, attendance/academics/announcements suites (unchanged by the remediation).

### 14.5 Readiness classification
**Development verification passed.**
Evidence: every required automated check in the table passed with exit 0, including the full students suite on the current code. Required for that label and **not** met by anything here: the items below. It is **not** "ready for staging validation" and not production-ready.

### 14.6 Still open (not resolved by tests)
1. **Unexplained application of certificates `0002` to the dev database** (13.2): cause undetermined; remains documented and unresolved. It is a separate matter from the test result; passing tests do not explain it.
2. **Owner decisions** from section 3 to 8: A (legacy TC exceptions), B (staff exit date; "employed to date" wording), C (retirement of legacy QR tokens and legacy seals, and whether legacy cards were printed), D (PDF download privacy), E (who holds the six permissions), F (non-Latin fonts and shaping).
3. **Migration policy:** forward-only once anything is issued (section 9); no bulk re-seal command exists.
4. **Staging prerequisites:** real keys (`CERTIFICATE_INTEGRITY_KEYS`/`ACTIVE_KEY`) supplied by the environment, `kdev` seals never carried over, and compatibility flags set deliberately.
5. **Testing gaps:** no frontend tests; no physical-printer check; on-screen ID card not rendered; the new student filters are not tested inside the students app.
