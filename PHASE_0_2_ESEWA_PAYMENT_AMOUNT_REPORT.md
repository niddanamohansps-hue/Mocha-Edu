# Phase 0.2 — eSewa Signup Payment Amount Report

## 1. Problem
The signup payment amount was hard-coded in two places:
- **Backend:** `backend/payments/views.py` `InitPaymentView` set `amount = "500"  # Fixed amount for now`. The string was used for the stored `Payment.amount`, the signed eSewa message, and the response.
- **Frontend:** `frontend/src/app/get-started/page.tsx` displayed the literal text `Rs. 500` on the payment panel.

## 2. Root Cause
The amount had no configuration source. Changing the price required a code change in two repositories, and the frontend could drift from the backend value.

Inspection findings:
- The amount was backend-owned for the actual payment (the eSewa form is built from the init response's `amount`, `signature`, and `transaction_uuid`), so the backend was already authoritative for what was charged.
- The frontend hard-coded only the displayed label.
- The amount was not previously configurable.

## 3. Solution
- **Configuration:** `backend/config/settings.py` adds `ESEWA_SIGNUP_PAYMENT_AMOUNT = config("ESEWA_SIGNUP_PAYMENT_AMOUNT", default="500")`, following the existing `ESEWA_*` settings and the decouple `config()` convention.
- **Single validator:** `backend/payments/utils.py` adds `get_signup_payment_amount()`. It is the only place the amount is read and validated, and it returns the exact string that is both signed and sent.
- **Views:** `InitPaymentView` calls the validator before creating any `Payment` row. The signature is generated over that same string.
- **Frontend:** the payment panel renders `Rs. {paymentData?.amount}`. The panel is only shown after `setPaymentData(response)`, so the value is always the backend's.
- **Example config:** `backend/.env.example` gains `ESEWA_SIGNUP_PAYMENT_AMOUNT=500`, with no real values.

### Validation rule
The value must match `\d+(\.\d{1,2})?` after trimming, be greater than 0, and be below `100000000` (the model is `max_digits=10, decimal_places=2`). Failures raise `PaymentConfigurationError`, the same exception the Phase 0.1 secret guard uses.

## 4. Default Behavior
- Unset variable: `config()` falls back to `"500"`, so existing deployments keep charging ₹500.
- Test `test_default_amount_preserves_existing_500` asserts the response amount is `"500"` and the stored record is `Decimal("500")`.

## 5. Custom Configuration
Example (non-secret) values:
```
ESEWA_SIGNUP_PAYMENT_AMOUNT=750
ESEWA_SIGNUP_PAYMENT_AMOUNT=750.50
```
With `750`, the response amount, the signed message (`total_amount=750,...`), and the `Payment.amount` all become `750`. Test `test_custom_amount_reaches_payload_signature_and_record` verifies the signature is computed over `750`.

## 6. Validation Behavior

| Configured value | Result |
|---|---|
| Missing (unset) | Default `500` used |
| Empty `""` or whitespace | Rejected, 503, no `Payment` row |
| Non-numeric (`abc`) | Rejected, 503, no `Payment` row |
| Zero (`0`, `0.00`) | Rejected, 503, no `Payment` row |
| Negative (`-5`) | Rejected, 503, no `Payment` row |
| `NaN`, `Infinity`, scientific notation (`1e3`) | Rejected, 503, no `Payment` row |
| More than 2 decimals (`750.555`) | Rejected, 503, no `Payment` row |
| At or above model limit (`100000000`) | Rejected, 503, no `Payment` row |

Rejections return `{"error": "Payment service is not configured."}` with HTTP 503 and log a fixed warning, `eSewa payment init rejected: signup payment amount is invalid.` The configured value is never logged or returned.

Validation happens at request time, not at settings load. This matches Phase 0.1 and avoids breaking deployments that do not use payments. The trade-off is that a bad value is noticed on the first payment attempt, not at startup.

## 7. Tests

### Added (`backend/payments/tests.py`, class `PaymentSignupAmountTest`)
1. `test_default_amount_preserves_existing_500`
2. `test_custom_amount_reaches_payload_signature_and_record` (750)
3. `test_decimal_amount_with_two_places_accepted` (750.50)
4. `test_invalid_amounts_rejected_without_creating_payment` (empty, whitespace, `abc`, `0`, `0.00`, `-5`, `NaN`, `Infinity`, `1e3`, `750.555`, `100000000`)
5. `test_phase_0_1_missing_secret_still_fails_closed_with_valid_amount`
6. `test_phase_0_1_empty_secret_still_fails_closed_with_valid_amount`

### Phase 0.1 regression
The `PaymentFailClosedTest` class and the `PaymentSecurityTest` tests from Phase 0.1 are unchanged and all pass.

### Isolation
Every test sets its values with `override_settings`. No environment variable is set globally.

### Results
- `./.venv/Scripts/python.exe manage.py check` — System check identified no issues.
- `./.venv/Scripts/python.exe manage.py test payments --keepdb` — **Ran 16 tests, OK** (10 from Phase 0.1 + 6 new).
- Frontend `tsc --noEmit` on `src/app/get-started/page.tsx`: no errors reported for the file. The full project type check was time-limited, so treat this as a file-level check, not a full build.

## 8. Files Changed
- `backend/config/settings.py` — adds `ESEWA_SIGNUP_PAYMENT_AMOUNT`.
- `backend/payments/utils.py` — adds `get_signup_payment_amount()` and its constants.
- `backend/payments/views.py` — `InitPaymentView` uses the validator instead of `"500"`.
- `backend/payments/tests.py` — adds `PaymentSignupAmountTest`; adds `Decimal` import.
- `backend/.env.example` — documents the new variable.
- `frontend/src/app/get-started/page.tsx` — displays `paymentData?.amount` instead of the literal `500`.

## 9. Database
No database changes.

## 10. Migrations
No migrations.

## 11. Git
- No commit.
- No push.
- Existing working-tree changes preserved. No destructive git commands were run.

## 12. Remaining Phase 0 Work
Not addressed in this phase:
- **Phase 0.3** — remove the committed student PDF under `backend/submissions/`.
- **Phase 0.4** — add tests for academics, staff, profiles, and organizations.

## Residual Risks
- **Placeholder secret in local `.env`:** `ESEWA_CLIENT_SECRET` is a non-empty placeholder, so Phase 0.1's guard passes locally. Production needs a real secret.
- **Signup amount is still not per-school:** the amount is one deployment-wide value. Per-plan or per-school pricing would need a model change and is out of scope.
- **Float comparison in verify:** `VerifyPaymentView` compares `float(total_amount)` with `float(payment.amount)`. It works for two-decimal values but is not an exact money comparison. Left unchanged, since changing verification is outside this phase.
- **Frontend display depends on the init response:** the label shows nothing until the backend responds, which is the existing flow.
