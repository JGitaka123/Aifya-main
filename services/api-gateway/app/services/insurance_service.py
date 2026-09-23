import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import Facility
from app.models.insurance import (
    InsuranceClaim,
    InsuranceScheme,
    PreAuthorization,
)
from app.models.patient import Patient
from app.schemas.insurance import (
    ClaimCreate,
    ClaimListItem,
    ClaimStatusUpdate,
    InsuranceSchemeCreate,
    InsuranceSummary,
)
from app.services.claimflow import ClaimFlowClient, ClaimValidationResult
from app.services.sha.submission import ShaSubmissionClient


class InsuranceService:
    """Service for insurance schemes, claims, and pre-authorization."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_scheme(
        self, data: InsuranceSchemeCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> InsuranceScheme:
        """
        Create an insurance scheme.

        @param data: Scheme data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created scheme
        """
        count = await self.db.execute(
            select(func.count(InsuranceScheme.id)).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count.scalar() or 0) + 1
        code = f"SCH-{seq:04d}"

        scheme = InsuranceScheme(
            facility_id=facility_id,
            name=data.name,
            scheme_code=code,
            scheme_type=data.scheme_type,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            address=data.address,
            contract_start=data.contract_start,
            contract_end=data.contract_end,
            coverage_details=data.coverage_details,
            rebate_percentage=data.rebate_percentage,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(scheme)
        await self.db.flush()
        await self.db.refresh(scheme)
        return scheme

    async def get_schemes(self, facility_id: uuid.UUID) -> list[InsuranceScheme]:
        """
        Get all active schemes.

        @param facility_id: Facility UUID
        @returns List of schemes
        """
        result = await self.db.execute(
            select(InsuranceScheme).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
            ).order_by(InsuranceScheme.name.asc())
        )
        return list(result.scalars().all())

    async def create_claim(
        self, data: ClaimCreate, facility_id: uuid.UUID, created_by: uuid.UUID
    ) -> InsuranceClaim:
        """
        Create an insurance claim.

        @param data: Claim data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created claim
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.claim_number.like(f"CLM-{date_part}-%"),
            )
        )
        seq = (count.scalar() or 0) + 1
        claim_number = f"CLM-{date_part}-{seq:04d}"

        claim = InsuranceClaim(
            facility_id=facility_id,
            claim_number=claim_number,
            patient_id=data.patient_id,
            scheme_id=data.scheme_id,
            invoice_id=data.invoice_id,
            encounter_id=data.encounter_id,
            member_number=data.member_number,
            claim_amount=data.claim_amount,
            status="draft",
            claim_date=now,
            claim_items=data.claim_items,
            diagnosis_codes=data.diagnosis_codes,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(claim)
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_claims(
        self, facility_id: uuid.UUID, status: str | None = None
    ) -> list[ClaimListItem]:
        """
        Get claims with patient and scheme names.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of claims
        """
        query = (
            select(
                InsuranceClaim,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
                InsuranceScheme.name.label("scheme_name"),
            )
            .join(Patient, InsuranceClaim.patient_id == Patient.id)
            .join(InsuranceScheme, InsuranceClaim.scheme_id == InsuranceScheme.id)
            .where(
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.is_deleted == False,  # noqa: E712
            )
        )
        if status:
            query = query.where(InsuranceClaim.status == status)
        query = query.order_by(InsuranceClaim.claim_date.desc())

        result = await self.db.execute(query)
        return [
            ClaimListItem(
                id=c.id,
                claim_number=c.claim_number,
                patient_id=c.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                scheme_name=sn,
                member_number=c.member_number,
                claim_amount=c.claim_amount,
                approved_amount=c.approved_amount,
                status=c.status,
                claim_date=c.claim_date,
            )
            for c, pf, pl, sn in result.all()
        ]

    async def get_claim(self, claim_id: uuid.UUID, facility_id: uuid.UUID) -> InsuranceClaim | None:
        """
        Get a single claim.

        @param claim_id: Claim UUID
        @param facility_id: Facility UUID
        @returns Claim or None
        """
        result = await self.db.execute(
            select(InsuranceClaim).where(
                InsuranceClaim.id == claim_id,
                InsuranceClaim.facility_id == facility_id,
                InsuranceClaim.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def validate_claim(
        self,
        claim_id: uuid.UUID,
        facility_id: uuid.UUID,
        auth_token: str | None = None,
        claimflow: ClaimFlowClient | None = None,
    ) -> tuple[InsuranceClaim | None, ClaimValidationResult | None]:
        """
        Run the ClaimFlow rule engine over a claim and persist the result.

        @param claim_id: Claim UUID
        @param facility_id: Facility UUID
        @param auth_token: Bearer token forwarded to the validator
        @param claimflow: Injectable client (tests)
        @returns Tuple of (claim, validation result) or (None, None) if not found
        """
        claim = await self.get_claim(claim_id, facility_id)
        if not claim:
            return None, None

        patient = await self.db.get(Patient, claim.patient_id)
        scheme = await self.db.get(InsuranceScheme, claim.scheme_id)
        facility = await self.db.get(Facility, facility_id)
        client = claimflow or ClaimFlowClient()

        result = await client.validate(
            claim=claim,
            patient=patient,
            scheme=scheme,
            facility=facility,
            auth_token=auth_token,
        )

        claim.validation_decision = result.decision
        claim.validation_result = {
            "total_rules": result.total_rules,
            "findings": result.findings,
            "fix_report_markdown": result.fix_report_markdown,
            "rulepack_version": result.rulepack_version,
        }
        claim.validated_at = datetime.now(UTC)
        await self.db.flush()
        return claim, result

    async def submit_claim(
        self,
        claim_id: uuid.UUID,
        facility_id: uuid.UUID,
        submitted_by: uuid.UUID,
        force: bool = False,
        sha_client: ShaSubmissionClient | None = None,
    ) -> tuple[InsuranceClaim | None, str]:
        """
        Submit a claim to SHA e-claims. Requires a prior validation that is
        not FAILED unless force is set (which records an override).

        @param claim_id: Claim UUID
        @param facility_id: Facility UUID
        @param submitted_by: Staff UUID
        @param force: Override a FAILED/absent validation (audited)
        @param sha_client: Injectable client (tests)
        @returns Tuple of (claim, message). claim is None if not found;
            message explains a refusal when the claim is unchanged.
        """
        claim = await self.get_claim(claim_id, facility_id)
        if not claim:
            return None, "not found"
        if claim.status not in ("draft",):
            return claim, f"Claim already {claim.status}; cannot resubmit"

        if not force:
            if claim.validation_decision is None:
                return claim, "Claim must be validated before submission"
            if claim.validation_decision == "FAILED":
                return claim, (
                    "Claim failed ClaimFlow validation; fix findings or submit "
                    "with force=true to override"
                )

        client = sha_client or ShaSubmissionClient()
        diagnoses = [str(d) for d in (claim.diagnosis_codes or [])]
        items = list(claim.claim_items or [])
        outcome = await client.submit(
            claim_number=claim.claim_number,
            member_number=claim.member_number,
            amount_cents=claim.claim_amount,
            diagnosis_codes=diagnoses,
            items=items,
        )

        now = datetime.now(UTC)
        if outcome.accepted:
            claim.status = "submitted"
            claim.submitted_date = now
            claim.sha_reference = outcome.sha_reference
            if force and claim.validation_decision == "FAILED":
                claim.notes = (
                    (claim.notes or "")
                    + f"\n[{now.isoformat()}] Submitted with validation override "
                    f"by {submitted_by}."
                )
            claim.updated_by = submitted_by
            await self.db.flush()
            return claim, outcome.message or "submitted"

        claim.rejection_reason = outcome.message
        claim.updated_by = submitted_by
        await self.db.flush()
        return claim, outcome.message

    async def update_claim_status(
        self, claim_id: uuid.UUID, data: ClaimStatusUpdate, facility_id: uuid.UUID, updated_by: uuid.UUID
    ) -> InsuranceClaim | None:
        """
        Update claim status.

        @param claim_id: Claim UUID
        @param data: Status update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated claim or None
        """
        claim = await self.get_claim(claim_id, facility_id)
        if not claim:
            return None

        now = datetime.now(UTC)
        claim.status = data.status
        if data.approved_amount is not None:
            claim.approved_amount = data.approved_amount
        if data.paid_amount is not None:
            claim.paid_amount = data.paid_amount
        if data.rejection_reason:
            claim.rejection_reason = data.rejection_reason
        if data.sha_reference:
            claim.sha_reference = data.sha_reference

        if data.status == "submitted":
            claim.submitted_date = now
        elif data.status in ("approved", "partially_approved", "rejected"):
            claim.processed_date = now
        elif data.status == "paid":
            claim.paid_date = now

        claim.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(claim)
        return claim

    async def get_summary(self, facility_id: uuid.UUID) -> InsuranceSummary:
        """
        Get insurance summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        base = [InsuranceClaim.facility_id == facility_id, InsuranceClaim.is_deleted == False]  # noqa: E712

        total = await self.db.execute(select(func.count(InsuranceClaim.id)).where(*base))
        pending = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "draft")
        )
        submitted = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "submitted")
        )
        approved = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(
                *base, InsuranceClaim.status.in_(["approved", "partially_approved"])
            )
        )
        rejected = await self.db.execute(
            select(func.count(InsuranceClaim.id)).where(*base, InsuranceClaim.status == "rejected")
        )
        value = await self.db.execute(
            select(func.sum(InsuranceClaim.claim_amount)).where(*base)
        )
        schemes = await self.db.execute(
            select(func.count(InsuranceScheme.id)).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.is_deleted == False,  # noqa: E712
                InsuranceScheme.is_active == True,  # noqa: E712
            )
        )
        preauth = await self.db.execute(
            select(func.count(PreAuthorization.id)).where(
                PreAuthorization.facility_id == facility_id,
                PreAuthorization.status == "pending",
            )
        )

        return InsuranceSummary(
            total_claims=total.scalar() or 0,
            pending_claims=pending.scalar() or 0,
            submitted_claims=submitted.scalar() or 0,
            approved_claims=approved.scalar() or 0,
            rejected_claims=rejected.scalar() or 0,
            total_claim_value=value.scalar() or 0,
            active_schemes=schemes.scalar() or 0,
            preauth_pending=preauth.scalar() or 0,
        )
