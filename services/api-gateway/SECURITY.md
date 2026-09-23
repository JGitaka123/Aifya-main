# API Gateway — Security Notes

## Field-level encryption at rest (Kenya DPA)

Sensitive employee PII is encrypted at rest via an application-level
`EncryptedString` SQLAlchemy type (`app/utils/encryption.py`, Fernet /
AES-128-CBC + HMAC):

- `employees.bank_account`
- `employees.id_number` (national ID)
- `employees.kra_pin`

Ciphertext is stored with a versioned `enc:v1:` prefix. Values written
before encryption was enabled (legacy plaintext, no prefix) are read back
transparently and re-encrypted on the next save, so no data is lost during
rollout.

### Key management

The key comes from `FIELD_ENCRYPTION_KEY` when set, otherwise it is derived
deterministically from `SECRET_KEY`. **Before production:**

1. Set an explicit, independently-rotatable `FIELD_ENCRYPTION_KEY`
   (`python -c "import secrets; print(secrets.token_hex(32))"`).
2. Store it in your secrets manager, not in `.env` committed anywhere.
3. Document custody and rotation. Rotating the key (or `SECRET_KEY` when no
   dedicated key is set) makes previously encrypted values unreadable —
   decrypt-then-re-encrypt with the old key available before rotating.

### Rollout

1. Apply migration `011_encrypt_employee_pii` (widens the columns).
2. Run `python -m scripts.backfill_employee_encryption` once to encrypt
   existing rows eagerly (optional — lazy backfill happens on save).

### Display

The payslip generator masks bank accounts to the last four digits
(`_mask_account`). `bank_account` is never returned in any API response
(`EmployeeResponse` omits it).

## Other security posture

See `docs/AUDIT-REPORT.md` for the full audit and remaining open items,
and `OPERATIONS.md` for the go-live checklist (non-superuser DB role for
RLS, M-Pesa callback IP allowlist, Sentry, deploy approval gate).
