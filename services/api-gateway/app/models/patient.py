from datetime import date

from sqlalchemy import Date, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Patient(AuditMixin, Base):
    """
    Patient demographics and registration data.
    Multi-tenant: every query filtered by facility_id from JWT.
    """

    __tablename__ = "patients"
    __table_args__ = (
        Index("ix_patients_facility_national_id", "facility_id", "national_id"),
        Index("ix_patients_facility_phone", "facility_id", "phone_number"),
        Index(
            "ix_patients_facility_name",
            "facility_id",
            "first_name",
            "last_name",
        ),
        Index("ix_patients_mrn", "facility_id", "mrn", unique=True),
    )

    # MRN (Medical Record Number) — facility-specific
    mrn: Mapped[str] = mapped_column(String(50), nullable=False)

    # Demographics
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str] = mapped_column(String(20), nullable=False)

    # Identification
    national_id: Mapped[str | None] = mapped_column(String(50))
    passport_number: Mapped[str | None] = mapped_column(String(50))

    # Contact
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    alternate_phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))

    # Address (Kenya-specific)
    county: Mapped[str | None] = mapped_column(String(100))
    sub_county: Mapped[str | None] = mapped_column(String(100))
    ward: Mapped[str | None] = mapped_column(String(100))
    village: Mapped[str | None] = mapped_column(String(200))
    postal_address: Mapped[str | None] = mapped_column(String(200))

    # Personal
    occupation: Mapped[str | None] = mapped_column(String(100))
    marital_status: Mapped[str | None] = mapped_column(String(20))

    # Next of Kin
    next_of_kin_name: Mapped[str | None] = mapped_column(String(200))
    next_of_kin_phone: Mapped[str | None] = mapped_column(String(20))
    next_of_kin_relationship: Mapped[str | None] = mapped_column(String(50))

    # Insurance
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_number: Mapped[str | None] = mapped_column(String(100))
    sha_number: Mapped[str | None] = mapped_column(String(50))

    # Medical
    blood_group: Mapped[str | None] = mapped_column(String(10))
    allergies: Mapped[list | None] = mapped_column(JSONB)
    chronic_conditions: Mapped[list | None] = mapped_column(JSONB)

    # Photo
    photo_url: Mapped[str | None] = mapped_column(String(500))

    # FHIR
    fhir_id: Mapped[str | None] = mapped_column(String(100))
