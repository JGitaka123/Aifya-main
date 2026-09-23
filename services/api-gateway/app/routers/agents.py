"""
Multi-Agent Clinical Workflows router.
Provides endpoints for running discharge, claims, and screening AI agents.
Per CLAUDE.md: AI NEVER auto-commits — all workflows return awaiting_clinician status.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.auth.license_check import require_module
from app.database import get_db
from app.services.agents.engine import AgentEngine
from app.services.agents.models import (
    AgentWorkflow,
    ClaimsAgentInput,
    DischargeAgentInput,
    ScreeningAgentInput,
)

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(require_module("encounters"))])


@router.post("/discharge", response_model=AgentWorkflow)
async def run_discharge_agent(
    input_data: DischargeAgentInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentWorkflow:
    """
    Run the discharge planning agent.
    Generates discharge summary, medication reconciliation, follow-up plan,
    and bilingual patient education materials.

    @param input_data: Discharge agent input with patient/encounter/admission IDs
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AgentWorkflow with discharge documents (requires clinician sign-off)
    """
    engine = AgentEngine(db)
    workflow = await engine.run_discharge_agent(input_data, current_user.facility_id)

    logger.info(
        "discharge_agent_complete",
        workflow_id=workflow.workflow_id,
        status=workflow.status,
        steps=len(workflow.steps),
        facility_id=str(current_user.facility_id),
    )
    return workflow


@router.post("/claims", response_model=AgentWorkflow)
async def run_claims_agent(
    input_data: ClaimsAgentInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentWorkflow:
    """
    Run the SHA claims automation agent.
    Maps diagnoses to SHA codes, validates claim, generates narrative,
    and packages for submission.

    @param input_data: Claims agent input with encounter/invoice/insurance IDs
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AgentWorkflow with SHA claim draft (requires clinician sign-off)
    """
    engine = AgentEngine(db)
    workflow = await engine.run_claims_agent(input_data, current_user.facility_id)

    logger.info(
        "claims_agent_complete",
        workflow_id=workflow.workflow_id,
        status=workflow.status,
        facility_id=str(current_user.facility_id),
    )
    return workflow


@router.post("/screening", response_model=AgentWorkflow)
async def run_screening_agent(
    input_data: ScreeningAgentInput,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AgentWorkflow:
    """
    Run the clinical trial screening agent.
    Matches patient against active trial criteria and generates a screening report.

    @param input_data: Screening input with patient ID and optional trial ID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns AgentWorkflow with trial match results (requires clinician sign-off)
    """
    engine = AgentEngine(db)
    workflow = await engine.run_screening_agent(input_data, current_user.facility_id)

    logger.info(
        "screening_agent_complete",
        workflow_id=workflow.workflow_id,
        status=workflow.status,
        facility_id=str(current_user.facility_id),
    )
    return workflow


@router.get("/types")
async def list_agent_types(
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """
    List available agent workflow types.

    @param current_user: Authenticated user from JWT
    @returns Available agent types with descriptions
    """
    return [
        {
            "type": "discharge",
            "name": "Discharge Planning Agent",
            "description": "AI-assisted discharge summary, medication reconciliation, follow-up plan, and bilingual patient education",
            "steps": 5,
        },
        {
            "type": "claims",
            "name": "SHA Claims Agent",
            "description": "Automated SHA claim preparation — code mapping, validation, narrative generation",
            "steps": 5,
        },
        {
            "type": "screening",
            "name": "Trial Screening Agent",
            "description": "AI clinical trial eligibility screening against active trial criteria",
            "steps": 3,
        },
    ]
