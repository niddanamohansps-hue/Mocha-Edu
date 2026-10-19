# Phase 6 Risk Remediation and Security Hardening

Status: development branch only. Nothing here has been applied to a real database, committed, or deployed.
Evidence for every statement below is either a test listed in section 11 or a stated inspection of the code.

## 1. Findings (confirmed defects vs. potential risks)

| # | Finding | Kind | Evidence |
|---|---|---|---|
| 1 | A TC could be issued when `Student.status` was Transferred/Withdrawn, with no proof of an authorized exit | Confirmed defect | `Student.status` is written only by the Promotion & Transfer service (`students/services.py`) and by Django admin. In the dev-data copy all 13 students with these statuses had **no** `PromotionRecord`. |
| 2 | Experience certificate could be issued for a **currently active** employee, and with an issuer-typed start date | Confirmed defect | No exit-date field exists on `StaffMember`; `is_active` is writable through the staff update serializer and admin. |
| 3 | ID-card QR token exposed the record UUID and the tenant schema name | Confirmed defect | A signed (not encrypted) token; the claims decode with no key. |
| 4 | Integrity HMAC keyed on `SECRET_KEY`: rotating it would break verification of every certificate | Confirmed design risk | Single unversioned key. |
| 5 | Viewers saw internal notes, internal user ids and (via the snapshot) a TC's date of birth | Confirmed defect | `CertificateSerializer` exposed them for any `view_certificates` holder, in list and detail. |
| 6 | Student/staff picker loaded at most 100 records and filtered in the browser | Confirmed limitation | Schools with more than 100 students could not find students beyond the first page. |
| 7 | Staff end date is not an authoritative record anywhere | **Open product/schema decision** | See section 4. Not fixed; mitigated and labelled. |
| 8 | Legacy students whose exit is not in the workflow cannot get a TC | **Open owner decision** | See section 3. |

## 2. What changed

Files modified: `backend/certificates/{models,services,views,serializers,urls,idcards,tests}.py`,
`backend/config/settings.py`, `backend/.env.example`, `backend/students/views.py` (search/status filter on the
existing list), `backend/staff/views.py` (search/is_active filter on the existing list),
`tenant_frontend/src/{hooks/useCertificates.ts,hooks/useStudents.ts,hooks/useStaff.ts,types/Certificates.ts}`,
`tenant_frontend/src/app/dashboard/{certificates/new,id-cards}/page.tsx`,
`tenant_frontend/src/components/dashboard/certificates/PersonPicker.tsx`.
Files created: `backend/certificates/tests_remediation.py`,
`backend/certificates/migrations/0002_alter_certificate_integrity_hash_idcardtoken.py` (generated, **not applied**),
this report.

## 3. Transfer Certificate authorization

**Rule now enforced (service layer, so every path is covered):** a TC requires
1. `approve_certificates` (unchanged),
2. `Student.status` in {transferred, withdrawn} (unchanged),
3. **a `PromotionRecord` for this same student whose action equals the current status** (newest transferred/withdrawn record).

Why this record is reliable: it is the only code path that sets those statuses; it is append-only; an exit record
cannot be reversed (`reverse_promotion` accepts only promoted/retained); it is a tenant-schema row, so another
tenant's records are unreachable. The proof (`exit_action`, `exit_recorded_on`) is stored on the certificate snapshot.
Issuing still changes no status, enrollment or history, and duplicates are blocked by the service and by the partial
unique index `cert_one_live_transfer_per_student`.

**Legacy students (status set outside the workflow) are refused with an explicit message.** I did not invent an
override. **Owner decision needed.** Proposed, narrowly scoped, audited override for approval:
- a separate permission `override_transfer_exit_check` (not granted to anyone by default),
- required free-text justification (min 20 chars) stored on the certificate and in the audit log
  (`certificate_issued_with_override`),
- the certificate and the public verification show no difference, but the staff detail view flags it,
- one use per student/TC (the live-TC constraint already guarantees this).
Alternative that needs no override: have the school record the exit through Promotion & Transfer, which requires the
student to be active with a current enrollment, so already-left students would first need to be re-activated. That is
a business-process question, not a code one.

## 4. Staff Experience Certificate dates

Inspection: `StaffMember` has `joining_date` (optional in onboarding serializers) and `is_active`; there is no
resignation/termination/relieving date in `staff`, `profiles` or `accounts`. `is_active` is flipped by the staff
update serializer and Django admin with no date captured. So **an exact verified end date does not exist.**

Implemented (no policy invented):
| Case | Behaviour |
|---|---|
| Current (active) employee | **Blocked.** "Employed to date" wording needs the owner's approval; not implemented. |
| Former employee | Allowed only when the joining date is on the record; start date always equals it. The issuer enters the end date (not future, not before start); it is stored as `end_date_source: issuer_entered` and written to the audit log. |
| Former employee, no verified end date | Still the issuer-entered date, **clearly labelled**; see decision below. |
| Missing joining date | **Blocked** ("add the joining date to the staff record"); a typed start date is rejected if it differs. |

**Owner decision / schema change required to make end dates authoritative (not implemented):**
add `StaffMember.exit_date` (nullable `DateField`) and `exit_reason`, set by a deactivation action that requires the
date; migration `staff/0003` adds nullable columns only. Backfill: **do not infer from `is_active`**; leave NULL and let
the owner enter dates for former staff. Affected workflows: staff update/deactivation, leave
(`is_active` checks), the experience-certificate service (would then require `exit_date` and refuse when NULL, retiring
the issuer-entered path). Until then the issuer-entered, labelled date is the only available input.

## 5. ID-card QR tokens

New table `IdCardToken` (tenant schema): random 192-bit token (`secrets.token_urlsafe(24)`, 32 chars), unique, one live
token per holder (partial unique indexes), exactly-one-subject check, `revoked_at`. The QR URL is
`/verify/id/<token>`; it carries no UUID, schema, enrollment/employee id or name. Verification looks the token up
**only inside the host's tenant schema**; unknown, malformed and revoked tokens return one identical minimal answer;
an inactive holder returns "inactive". The endpoint stays throttled (60/min). Staff can **replace a card's QR code**
(`POST /api/certificates/id-cards/<kind>/<id>/rotate/`, `generate_id_cards`): the old token is revoked, the audit log
records the revoked row id and the last 4 characters of the new token, never the secret.

**Old printed cards.** Nothing was ever recorded server-side for old cards, so how many were printed is unknowable
from the database (the dev DB has zero certificates; whether ID cards were printed is a fact only the owner has).
Deliberate handling: legacy signed tokens keep verifying **read-only** while `ID_CARD_ACCEPT_LEGACY_TOKENS=True`
(default), and are never produced again. They still contain the record UUID and schema name, but only to someone who
holds that already-printed card. **Retirement:** reprint cards, then set the flag to `False`; every legacy code then
answers "invalid". **Owner decision:** set a retirement date.

Migration `0002` (additive): creates `certificates_idcardtoken`; widens `certificate.integrity_hash` 64 -> 128.
Rollback: `migrate_schemas certificates 0001` drops the token table (tokens are re-creatable by regenerating cards)
and shrinks the column back to 64, **which fails once any v2 seal (67+ chars) exists**; after rollout begins, restore
from backup instead of reversing.

## 6. Integrity HMAC key rotation

Signed: the canonical JSON of the printed content, ids, status, issuer/approver and schema name, with HMAC-SHA256.
It protects stored certificate records only (the public verifier recomputes it; ID cards no longer use any signature).
New format `k<keyid>:<hex>`; keys come from `CERTIFICATE_INTEGRITY_KEYS="1:secret,2:secret"` and
`CERTIFICATE_INTEGRITY_ACTIVE_KEY`. They are independent of `SECRET_KEY`. Behaviour (all tested):
- verification uses the key the seal names; retired/unknown key, bad digest or bad format => **fails closed** (the
  public page shows "could not be verified");
- sealing without a usable active key raises and aborts the whole issue (no number consumed);
- outside `DEBUG` settings refuse to start without keys (same pattern as `FIELD_ENCRYPTION_KEY`); in `DEBUG` a
  labelled `dev` key is used and is never honoured in production;
- legacy unversioned digests (made with `SECRET_KEY`) verify only while `CERTIFICATE_ACCEPT_LEGACY_SEALS=True`, and
  are never produced again; any status change re-seals under the active key.

**Rotation procedure (documented, not executed):** (1) generate a secret
(`python -c "import secrets; print(secrets.token_urlsafe(48))"`); (2) add `2:<secret>` and keep `1`; (3) set ACTIVE to
`2`, deploy; new/changed certificates use key 2, old ones keep verifying with key 1; (4) when no certificate references
key 1 (query `integrity_hash LIKE 'k1:%'` per tenant) remove it. Never reuse an id; never delete a key that is still
referenced. **Not done:** a bulk re-seal command (re-sealing happens on status change); proposed if wanted.
**Existing dev DB:** its certificate tables are empty, so nothing needs migrating there. Any certificate sealed by the
earlier build (bare digest) stays verifiable under the legacy flag.

## 7. Certificate privacy and access

- JSON never includes the snapshot (it can hold a TC's date of birth; it is only printed on the PDF).
- List rows: identification and status only.
- Single certificate: `view_certificates` alone gets no internal notes, no internal user/record ids, no verification id.
  Holders of `issue_`, `approve_` or `cancel_certificates` see the full record (registrar/principal workflows kept).
- Public verification unchanged (minimal), unauthenticated/other-tenant requests unchanged (403/404).
- No new permission was introduced; existing permissions gate the two tiers.
**Residual (owner decision):** a `view_certificates` holder can still download the **PDF**, which prints the TC's date
of birth. That is the issued document itself; restrict PDF download to issuers/approvers if viewers should not see it.

## 8. Picker

`GET /api/students/list/` gains `search` (up to 5 terms; names or admission number), `status` (comma list, validated);
`GET /api/staff/members/` gains `search` and `is_active`. Existing permissions (`view_student`, `view_staff`),
tenant scoping and pagination (20 default, hard cap 100) are unchanged. The picker searches on the server with a
300 ms debounce and pages 20 at a time; transfer lists only students who have left, experience lists only inactive staff.

## 9. Permission matrix (proposal; nothing assigned automatically)

Existing: all six are held by **owner only** in every tenant (verified in the rehearsal copy).

| Permission | Existing | Proposed | Needs owner approval |
|---|---|---|---|
| `view_certificates` | owner | registrar / office staff; principal | yes |
| `issue_certificates` (bonafide, character) | owner | registrar / office staff | yes |
| `approve_certificates` (TC, experience) | owner | principal / tenant admin only | yes |
| `cancel_certificates` (cancel/reissue) | owner | principal / tenant admin only | yes |
| `manage_certificate_settings` (signatory) | owner | tenant admin only | yes |
| `generate_id_cards` (incl. replace QR) | owner | office / admin staff | yes |
| `override_transfer_exit_check` (**proposed, not created**) | - | principal only, if the override is approved | yes |
Picking people also needs `view_student` / `view_staff`. Who issues TCs: principal-level (`approve`); experience
certificates: principal-level (`approve`); cancel/reissue: principal-level; signatory settings: tenant admin.

## 10. Owner decisions still required

1. TC legacy-exit override: approve the proposal in section 3, or re-record exits through the workflow.
2. Staff `exit_date` schema change and backfill plan (section 4); wording for current employees ("to date").
3. Retirement date for legacy ID-card tokens and legacy certificate seals.
4. Whether `view_certificates`-only users may download PDFs that print a date of birth.
5. Who gets each permission (section 9); non-Latin font (carried over from validation).

## 11. Verification

See the final test results appended by the run (below).
