"""
Referral templates — facility-managed standardized referral note prefills.
"""

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class ReferralTemplate(AuditMixin, Base):
    """
    Reusable referral note template by specialty.
    The `template_text` is markdown / plaintext used to prefill the
    clinical_notes / reason fields when a clinician creates a referral.
    """

    __tablename__ = "referral_templates"
    __table_args__ = (
        Index("ix_referral_templates_specialty", "facility_id", "specialty"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialty: Mapped[str] = mapped_column(String(100), nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
