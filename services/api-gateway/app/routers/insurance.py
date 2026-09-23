import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.insurance import (
    ClaimCreate,
    ClaimListResponse,
    ClaimResponse,
    ClaimStatusUpdate,
    ClaimSubmitRequest,
    ClaimSubmitResponse,
    ClaimValidationResponse,
    InsuranceSchemeCreate,
    InsuranceSchemeListResponse,
    InsuranceSchemeResponse,
    InsuranceSummary,
)
from app.services.insurance_service import InsuranceService
from app.services.sha.validation import ShaMember
from app.services.sha.validation import validate_member as validate_sha_member

router = APIRouter(dependencies=[Depends(require_module("insurance"))])


@router.get("/summary", response_model=InsuranceSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InsuranceSummary:
    """
    Get insurance summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Insurance summary
    """
    service = InsuranceService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


@router.get("/schemes", response_model=InsuranceSchemeListResponse)
async def list_schemes(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InsuranceSchemeListResponse:
    """
    Get insurance schemes.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Scheme list
    """
    service = InsuranceService(db)
    schemes = await service.get_schemes(facility_id=current_user.facility_id)
    return InsuranceSchemeListResponse(
        items=[InsuranceSchemeResponse.model_validate(s) for s in schemes],
        total=len(schemes),
    )


@router.post("/schemes", response_model=InsuranceSchemeResponse, status_code=status.HTTP_201_CREATED)
async def create_scheme(
    data: InsuranceSchemeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin")),
) -> InsuranceSchemeResponse:
    """
    Create an insurance scheme.

    @param data: Scheme data
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Created scheme
    """
    service = InsuranceService(db)
    scheme = await service.create_scheme(data=data, facility_id=current_user.facility_id, created_by=current_user.user_id)
    return InsuranceSchemeResponse.model_validate(scheme)


@router.get("/claims", response_model=ClaimListResponse)
async def list_claims(
    claim_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClaimListResponse:
    """
    Get insurance claims.

    @param claim_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Claim list
    """
    service = InsuranceService(db)
    items = await service.get_claims(facility_id=current_user.facility_id, status=claim_status)
    return ClaimListResponse(items=items, total=len(items))


@router.post("/claims", response_model=ClaimResponse, status_code=status.HTTP_201_CREATED)
async def create_claim(
    data: ClaimCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "billing_officer")
    ),
) -> ClaimResponse:
    """
    Create an insurance claim.

    @param data: Claim data
    @param db: Database session
    @param current_user: Authenticated billing/admin staff
    @returns Created claim
    """
    service = InsuranceService(db)
    claim = await service.create_claim(data=data, facility_id=current_user.facility_id, created_by=current_user.user_id)
    return ClaimResponse.model_validate(claim)


@router.get("/claims/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClaimResponse:
    """
    Get a single claim.

    @param claim_id: Claim UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Claim details
    """
    service = InsuranceService(db)
    claim = await service.get_claim(claim_id, current_user.facility_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimResponse.model_validate(claim)


@router.get("/sha/validate", response_model=ShaMember)
async def validate_sha_membership(
    sha_number: str = Query(..., min_length=3, max_length=50),
    id_number: str = Query(..., min_length=3, max_length=20),
    current_user: CurrentUser = Depends(get_current_user),
) -> ShaMember:
    """
    Validate a SHA (Social Health Authority) member.
    Caches results for 24h. Returns mock data when SHA API is not configured
    so dev environments can keep working.

    @param sha_number: SHA membership number
    @param id_number: National ID or passport number
    @param current_user: Authenticated user from JWT
    @returns SHA member details (status, scheme, dependents)
    @raises HTTPException 404: If member is not found
    """
    member = await validate_sha_member(sha_number=sha_number, id_number=id_number)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SHA member not found",
        )
    return member


@router.post(
    "/claims/{claim_id}/validate", response_model=ClaimValidationResponse
)
async def validate_claim(
    claim_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "billing_officer")
    ),
) -> ClaimValidationResponse:
    """
    Run the ClaimFlow SHA rule engine over a claim before submission and
    store the result. Returns the decision and remediation findings.

    @param claim_id: Claim UUID
    @param request: Incoming request (to forward the bearer token)
    @param db: Database session
    @param current_user: Authenticated billing/admin staff
    @returns Validation decision, findings, and fix report
    """
    auth_header = request.headers.get("authorization", "")
    token = auth_header[7:] if auth_header.lower().startswith("bearer ") else None
    service = InsuranceService(db)
    claim, result = await service.validate_claim(
        claim_id=claim_id, facility_id=current_user.facility_id, auth_token=token
    )
    if not claim or result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimValidationResponse(
        claim_id=claim.id,
        decision=result.decision,
        total_rules=result.total_rules,
        findings=result.findings,
        fix_report_markdown=result.fix_report_markdown,
        rulepack_version=result.rulepack_version,
    )


@router.post("/claims/{claim_id}/submit", response_model=ClaimSubmitResponse)
async def submit_claim(
    claim_id: uuid.UUID,
    data: ClaimSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "billing_officer")
    ),
) -> ClaimSubmitResponse:
    """
    Submit a validated claim to SHA e-claims. Requires a prior validation
    that is not FAILED unless force is set.

    @param claim_id: Claim UUID
    @param data: Submit request (force override)
    @param db: Database session
    @param current_user: Authenticated billing/admin staff
    @returns The claim plus acceptance status and message
    """
    service = InsuranceService(db)
    claim, message = await service.submit_claim(
        claim_id=claim_id,
        facility_id=current_user.facility_id,
        submitted_by=current_user.user_id,
        force=data.force,
    )
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    accepted = claim.status == "submitted"
    if not accepted and message and claim.status == "draft" and (
        "must be validated" in message or "failed ClaimFlow" in message
    ):
        # A policy refusal (not found handled above) — 409 Conflict.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message)
    return ClaimSubmitResponse(
        claim=ClaimResponse.model_validate(claim),
        accepted=accepted,
        message=message,
    )


@router.post("/claims/{claim_id}/status", response_model=ClaimResponse)
async def update_claim_status(
    claim_id: uuid.UUID,
    data: ClaimStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "billing_officer")
    ),
) -> ClaimResponse:
    """
    Update claim status.

    @param claim_id: Claim UUID
    @param data: Status update
    @param db: Database session
    @param current_user: Authenticated billing/admin staff
    @returns Updated claim
    """
    service = InsuranceService(db)
    claim = await service.update_claim_status(
        claim_id=claim_id, data=data, facility_id=current_user.facility_id, updated_by=current_user.user_id
    )
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return ClaimResponse.model_validate(claim)
