"""One-off: eagerly encrypt existing plaintext employee PII.

The EncryptedString column type reads legacy plaintext transparently and
re-encrypts on next save, so this is optional — but run it once after
deploying migration 011 to encrypt existing rows immediately rather than
waiting for each employee record to be edited.

Usage (inside the api-gateway container / venv):
    python -m scripts.backfill_employee_encryption
"""

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.models.payroll import Employee
from app.utils.encryption import _ENC_PREFIX


async def _needs_encryption(raw: str | None) -> bool:
    """Whether a stored value is still legacy plaintext."""
    return bool(raw) and not raw.startswith(_ENC_PREFIX)


async def main() -> None:
    """Re-save every employee so encrypted columns are written as ciphertext."""
    async with async_session() as session:
        result = await session.execute(select(Employee))
        employees = list(result.scalars().all())
        updated = 0
        for emp in employees:
            # Reading already decrypted the values; re-assigning marks the
            # attributes dirty so the flush re-encrypts them.
            emp.id_number = emp.id_number
            emp.kra_pin = emp.kra_pin
            emp.bank_account = emp.bank_account
            updated += 1
        await session.commit()
        print(f"[backfill] re-encrypted PII for {updated} employee(s)")


if __name__ == "__main__":
    asyncio.run(main())
