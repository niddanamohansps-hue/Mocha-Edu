# Phase 0.1 — eSewa Secret Security Report

## Problem
`ESEWA_CLIENT_SECRET` defaulted to an empty string. The payment flow would sign payment requests and verify eSewa callbacks using an empty HMAC key, which is publicly predictable. A misconfigured deployment could therefore accept forged "COMPLETE" callbacks.

## Root Cause
- `backend/config/settings.py` — `ESEWA_CLIENT_SECRET = config("ESEWA_CLIENT_SECRET", default="")`. A missing environment variable produced `""` with no error at startup or at runtime.
- `backend/payments/views.py` — `InitPaymentView` and `VerifyPaymentView` passed `settings.ESEWA_CLIENT_SECRET` straight into `generate_esewa_signature`, which performed HMAC with whatever key it received, including an empty one.
- `backend/payments/utils.py` — `generate_esewa_signature` had no key validation.

## Design Decision
The project has no "payments enabled" flag. eSewa is used only by the public signup path. A startup-time requirement (the `FIELD_ENCRYPTION_KEY` pattern) would break every deployment that does not take payments. The fix therefore fails closed at the point of use: any payment operation without a secret is rejected.

## Solution
1. **Settings** — `ESEWA_CLIENT_SECRET` now defaults to `None` (no empty-string default).
2. **Central guard** — `payments/utils.py` adds `get_esewa_secret()`, which raises `PaymentConfigurationError` when the secret is missing or falsy.
3. **Signing refusal** — `generate_esewa_signature()` itself refuses a missing or empty key, so no caller can sign with an empty key.
4. **Init** — `InitPaymentView` checks the secret before creating any `Payment` row.
5. **Verify** — `VerifyPaymentView` checks the secret before reading the callback at all.
6. **Response** — on missing secret both views return HTTP 503 with `{"error": "Payment service is not configured."}`.
7. **Logging** — a warning is logged with a fixed message and no secret value.

## Security Behavior

| Secret state | Init (`POST /api/payments/init/`) | Verify (`GET /api/payments/verify/`) |
|---|---|---|
| Missing (`None`) | 503, no `Payment` row created, no signature | 503, payment stays PENDING, no tenant created |
| Empty (`""`) | 503, no `Payment` row created, no signature | 503, payment stays PENDING, no tenant created |
| Valid | 200, HMAC signature as before | Signature verified as before |

## Tests Added
In `backend/payments/tests.py`, class `PaymentFailClosedTest`:
- `test_init_rejects_missing_secret_and_creates_no_payment`
- `test_init_rejects_empty_secret_and_creates_no_payment`
- `test_verify_with_valid_signature_is_rejected_when_secret_later_removed`
- `test_verify_rejects_malformed_callback_when_secret_missing`
- `test_signing_helper_refuses_missing_and_empty_keys`
- `test_valid_secret_still_signs_and_verifies`
- `test_secret_never_appears_in_logs_on_rejection`

Also changed: the existing `PaymentSecurityTest` now uses `override_settings` with a synthetic secret (`test-esewa-secret-not-production`) instead of permanently overwriting `settings.ESEWA_CLIENT_SECRET`.

## Tests Executed
- `./.venv/Scripts/python.exe manage.py check` — System check identified no issues.
- `./.venv/Scripts/python.exe manage.py test payments --keepdb` — **Ran 10 tests, OK.**
  - First run: 9 passed, 1 failed (`test_valid_secret_still_signs_and_verifies`). Cause: the test hard-coded product code `EPAYTEST`, but the local `.env` sets `ESEWA_PRODUCT_CODE` to a placeholder. Fixed by pinning `ESEWA_PRODUCT_CODE` in that test. The fix is in the test only.

## Files Changed
- `backend/config/settings.py` — `ESEWA_CLIENT_SECRET` default `""` → `None`, with a comment.
- `backend/payments/utils.py` — `PaymentConfigurationError`, `get_esewa_secret()`, key check in `generate_esewa_signature()`.
- `backend/payments/views.py` — guard in `InitPaymentView` and `VerifyPaymentView`; `logging` import; signature calls use the guarded secret.
- `backend/payments/tests.py` — `override_settings` isolation; new `PaymentFailClosedTest`.

## Files Not Changed
No other module was touched. Payment amount (`amount = "500"`), signup logic, fee logic, allocation logic, and the eSewa product code/URL were not modified.

## Remaining Phase 0 Items (NOT addressed here)
- **Hard-coded signup amount** (`amount = "500"`) — Phase 0.2.
- **Committed student PDF** under `backend/submissions/` — Phase 0.3.
- **Missing tests** in academics, staff, profiles, organizations — Phase 0.4.
- **Celery orchestration** — not in scope.
- **Throttling review** — not in scope.

## Residual Risk Noted (not changed in this phase)
The guard checks **presence**, not **strength**. The local `.env` sets `ESEWA_CLIENT_SECRET=your-esewa-client-secret`, a non-empty placeholder, so the guard passes in this environment. Production must set a real, high-entropy secret. A follow-up could reject known placeholder values, but that was not added here to keep the change minimal.
