"""Tests that sensitive employee PII is encrypted at rest (Kenya DPA)."""

import pytest
from sqlalchemy import text

from app.models.payroll import Employee
from app.utils.encryption import decrypt_value, encrypt_value
from tests.conftest import FACILITY_ID
from tests.conftest import session_factory as _session_factory


def test_encrypt_decrypt_round_trip() -> None:
    """encrypt_value/decrypt_value are inverse and produce ciphertext."""
    plaintext = "1234567890"
    token = encrypt_value(plaintext)
    assert token != plaintext
    assert token.startswith("enc:v1:")
    assert decrypt_value(token) == plaintext


def test_legacy_plaintext_reads_through() -> None:
    """Pre-encryption plaintext (no prefix) is returned unchanged."""
    assert decrypt_value("A012345678Z") == "A012345678Z"


@pytest.mark.asyncio
async def test_employee_pii_stored_encrypted() -> None:
    """Bank account, national ID and KRA PIN are ciphertext in the DB,
    but read back decrypted through the ORM."""
    async with _session_factory() as session:
        emp = Employee(
            facility_id=FACILITY_ID,
            staff_id="EMP-ENC-1",
            full_name="Encrypted Employee",
            id_number="29384756",
            kra_pin="A001234567Z",
            hire_date=__import__("datetime").date(2020, 1, 1),
            bank_account="0110123456789",
        )
        session.add(emp)
        await session.commit()
        emp_id = emp.id

    # Raw SQL bypasses the ORM type decorator — must see ciphertext.
    async with _session_factory() as session:
        row = await session.execute(
            text(
                "SELECT bank_account, id_number, kra_pin "
                "FROM employees WHERE staff_id = :sid"
            ),
            {"sid": "EMP-ENC-1"},
        )
        raw_bank, raw_id, raw_kra = row.one()
        assert raw_bank.startswith("enc:v1:")
        assert "0110123456789" not in raw_bank
        assert raw_id.startswith("enc:v1:")
        assert raw_kra.startswith("enc:v1:")

    # ORM read decrypts transparently.
    async with _session_factory() as session:
        emp = await session.get(Employee, emp_id)
        assert emp is not None
        assert emp.bank_account == "0110123456789"
        assert emp.id_number == "29384756"
        assert emp.kra_pin == "A001234567Z"
