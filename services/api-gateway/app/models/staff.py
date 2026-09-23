import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Department(AuditMixin, Base):
    """Hospital department (e.g., Outpatient, Surgery, Pharmacy, Lab)."""

    __tablename__ = "departments"
    __table_args__ = (
        Index("ix_departments_facility_code", "facility_id", "code", unique=True),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    department_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # clinical, support, admin
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    head_of_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class Staff(AuditMixin, Base):
    """
    Staff member (doctor, nurse, pharmacist, lab tech, admin, etc.).
    Linked to Keycloak user via keycloak_user_id.
    """

    __tablename__ = "staff"
    __table_args__ = (
        Index("ix_staff_facility_keycloak", "facility_id", "keycloak_user_id", unique=True),
        Index("ix_staff_facility_employee_number", "facility_id", "employee_number", unique=True),
    )

    # Identity
    keycloak_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    employee_number: Mapped[str] = mapped_column(String(50), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Professional
    title: Mapped[str | None] = mapped_column(String(50))  # Dr., Nurse, etc.
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # doctor, nurse, pharmacist, lab_tech, admin, cashier, records
    specialization: Mapped[str | None] = mapped_column(String(100))
    license_number: Mapped[str | None] = mapped_column(String(50))
    license_body: Mapped[str | None] = mapped_column(
        String(100)
    )  # KMPDC, NCK, PPB, KMLTTB

    # Department
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )
    primary_department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )

    # Contact
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Permissions (supplemental to Keycloak roles)
    permissions: Mapped[dict | None] = mapped_column(JSONB)

    # Digital signature for prescriptions / clinical sign-off
    signature_url: Mapped[str | None] = mapped_column(String(500))

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
