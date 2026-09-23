import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.dental import (
    DentalChartResponse,
    DentalChartUpdate,
    DentalSummary,
    DentalTreatmentPlanCreate,
    DentalTreatmentPlanListResponse,
    DentalTreatmentPlanResponse,
    DentalTreatmentPlanStatusUpdate,
    DentalVisitCreate,
    DentalVisitListResponse,
    DentalVisitResponse,
)
from app.services.dental_service import DentalService

router = APIRouter(dependencies=[Depends(require_module("dental"))])


@router.get("/summary", response_model=DentalSummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DentalSummary:
    """
    Get dental department summary.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Dental summary
    """
    service = DentalService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


@router.get("/charts/{patient_id}", response_model=DentalChartResponse)
async def get_chart(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DentalChartResponse:
    """
    Get or create a dental chart for a patient.

    @param patient_id: Patient UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Dental chart
    """
    service = DentalService(db)
    chart = await service.get_or_create_chart(
        patient_id=patient_id,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return DentalChartResponse.model_validate(chart)


@router.put("/charts/{patient_id}", response_model=DentalChartResponse)
async def update_chart(
    patient_id: uuid.UUID,
    data: DentalChartUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "dentist")
    ),
) -> DentalChartResponse:
    """
    Update dental chart.

    @param patient_id: Patient UUID
    @param data: Chart update data
    @param db: Database session
    @param current_user: Authenticated dentist/doctor
    @returns Updated chart
    """
    service = DentalService(db)
    chart = await service.update_chart(
        patient_id=patient_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    return DentalChartResponse.model_validate(chart)


@router.get("/visits", response_model=DentalVisitListResponse)
async def list_visits(
    patient_id: uuid.UUID | None = Query(None, description="Filter by patient"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DentalVisitListResponse:
    """
    Get dental visits.

    @param patient_id: Optional patient filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Visit list
    """
    service = DentalService(db)
    items = await service.get_visits(
        facility_id=current_user.facility_id,
        patient_id=patient_id,
    )
    return DentalVisitListResponse(items=items, total=len(items))


@router.post("/visits", response_model=DentalVisitResponse, status_code=status.HTTP_201_CREATED)
async def create_visit(
    data: DentalVisitCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "dentist")
    ),
) -> DentalVisitResponse:
    """
    Create a dental visit.

    @param data: Visit data
    @param db: Database session
    @param current_user: Authenticated dentist/doctor
    @returns Created visit
    """
    service = DentalService(db)
    visit = await service.create_visit(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return DentalVisitResponse.model_validate(visit)


@router.get("/visits/{visit_id}", response_model=DentalVisitResponse)
async def get_visit(
    visit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DentalVisitResponse:
    """
    Get a dental visit.

    @param visit_id: Visit UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Visit details
    """
    service = DentalService(db)
    visit = await service.get_visit(visit_id, current_user.facility_id)
    if not visit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dental visit not found")
    return DentalVisitResponse.model_validate(visit)


@router.get("/treatment-plans", response_model=DentalTreatmentPlanListResponse)
async def list_treatment_plans(
    patient_id: uuid.UUID | None = Query(None, description="Filter by patient"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DentalTreatmentPlanListResponse:
    """
    Get dental treatment plans.

    @param patient_id: Optional patient filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Treatment plan list
    """
    service = DentalService(db)
    plans = await service.get_treatment_plans(
        facility_id=current_user.facility_id,
        patient_id=patient_id,
    )
    return DentalTreatmentPlanListResponse(items=plans, total=len(plans))


@router.post(
    "/treatment-plans",
    response_model=DentalTreatmentPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_treatment_plan(
    data: DentalTreatmentPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "dentist")
    ),
) -> DentalTreatmentPlanResponse:
    """
    Create a dental treatment plan.

    @param data: Plan data
    @param db: Database session
    @param current_user: Authenticated dentist/doctor
    @returns Created plan
    """
    service = DentalService(db)
    plan = await service.create_treatment_plan(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return DentalTreatmentPlanResponse.model_validate(plan)


@router.patch(
    "/treatment-plans/{plan_id}/status",
    response_model=DentalTreatmentPlanResponse,
)
async def update_treatment_plan_status(
    plan_id: uuid.UUID,
    data: DentalTreatmentPlanStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "doctor", "dentist")
    ),
) -> DentalTreatmentPlanResponse:
    """
    Move a dental treatment plan through its lifecycle.

    @param plan_id: Treatment plan UUID
    @param data: Target status
    @param db: Database session
    @param current_user: Authenticated dentist/doctor
    @returns Updated plan
    """
    service = DentalService(db)
    plan = await service.update_treatment_plan_status(
        plan_id=plan_id,
        new_status=data.status,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Treatment plan not found",
        )
    return DentalTreatmentPlanResponse.model_validate(plan)
