"""One-off: widen employee ciphertext columns past the VARCHAR(20) cap.

Fix for `asyncpg.exceptions.StringDataRightTruncationError: value too long
for type character varying(20)` when adding an employee. The app stores
National ID / KRA PIN / bank account as Fernet ciphertext (~108 chars), which
does not fit columns created as VARCHAR(20). This script widens every column
that can receive ciphertext.

Usage (inside the api-gateway folder, using the venv):
    .venv\Scripts\python.exe -m scripts.fix_employee_column_widths
"""

import asyncio

from sqlalchemy import text

from app.database import engine


# (table, column) pairs that store (or receive) Fernet ciphertext.
_TARGETS = [
    ("employees", "id_number"),
    ("employees", "kra_pin"),
    ("employees", "bank_account"),
    ("staff_profiles", "national_id"),
    ("staff_profiles", "kra_pin"),
    ("staff_profiles", "nssf_number"),
    ("staff_profiles", "nhif_number"),
]


async def main() -> None:
    """Widen each target column to VARCHAR(255) and report the outcome."""
    async with engine.begin() as conn:
        for table, column in _TARGETS:
            try:
                await conn.execute(
                    text(
                        f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                        "TYPE VARCHAR(255)"
                    )
                )
                print(f"[ok] {table}.{column} -> VARCHAR(255)")
            except Exception as exc:  # noqa: BLE001 - report per-column and continue
                print(f"[skip] {table}.{column}: {exc.__class__.__name__}")
    print("done - restart uvicorn and retry Add Employee")


if __name__ == "__main__":
    asyncio.run(main())
