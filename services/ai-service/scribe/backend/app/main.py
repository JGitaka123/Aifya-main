import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request, APIRouter, HTTPException, status, Query, Body, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from structlog import get_logger

from app.config import get_settings
from app.models import (
    HealthResponse, UserRole, TranscriptInput, ScrubRequest, DischargeRequest,
    SyncNoteRequest, UserCreate, UserResponse, TokenResponse,
    ScrubStatus, ClaimStatus, DischargeStatus, LoginRequest, ClaimOverrideRequest,
    DischargeStatusUpdate, SyncDischargeRequest, AdminUserCreate,
)
from app.auth.auth import (
    RoleChecker, get_current_user_token_payload,
    create_access_token, create_refresh_token,
    get_password_hash, verify_password,
    verify_refresh_token,
    oauth2_scheme,
)
from app.middleware import AuditLoggingMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware
from app.adapters.qafya_adapter import QAfyaAdapter
from app.rules.sha_engine import SHARulesEngine
from app.nlp.nlp_engine import NLPEngine
from app.discharge.discharge_engine import DischargeEngine, DischargeEngineException

logger = get_logger(__name__)
settings = get_settings()

# -----------------
# Application State
# -----------------
qafya_adapter = QAfyaAdapter(settings.qafya)
sha_engine = SHARulesEngine()
nlp_engine = NLPEngine()
discharge_engine = DischargeEngine(qafya=qafya_adapter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_startup_sequence", status="starting")
    await qafya_adapter.connect()
    await qafya_adapter.validate_schema_on_startup()
    logger.info("app_startup_sequence", status="complete")
    yield
    logger.info("app_shutdown_sequence", status="starting")
    await qafya_adapter.close()
    logger.info("app_shutdown_sequence", status="complete")


# -----------------
# FastAPI Config
# -----------------
# Disable OpenAPI/Swagger docs in production to avoid exposing API surface
_is_dev: bool = settings.app_env == "development" or settings.debug
_docs_url: str | None = "/docs" if _is_dev else None
_openapi_url: str | None = f"{settings.api_v1_str}/openapi.json" if _is_dev else None

app = FastAPI(
    title=settings.project_name,
    openapi_url=_openapi_url,
    docs_url=_docs_url,
    redoc_url=None,
    lifespan=lifespan,
)

# -----------------
# Middleware Stack (order matters: last added = first executed)
# -----------------
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# -----------------
# Router
# -----------------
router = APIRouter(prefix=settings.api_v1_str)


# =====================
# HEALTH CHECK
# =====================
@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health_check() -> HealthResponse:
    """Minimal health check endpoint. Returns component status without leaking config.

    @returns: HealthResponse with status and component health indicators.
    """
    db_status = "disconnected"
    if qafya_adapter.pool:
        try:
            rows = await qafya_adapter._execute_read("SELECT 1")
            db_status = "connected" if rows else "degraded"
        except Exception:
            db_status = "error"

    llm_status = "configured" if settings.openai_api_key and settings.openai_api_key != "sk-proj-youropenaiapikeyhere..." else "not_configured"

    return HealthResponse(
        status="ok",
        components={
            "api": "healthy",
            "qafya_db": db_status,
            "llm_api": llm_status,
        },
    )


# =====================
# AUTH ENDPOINTS
# =====================
@router.post(
    "/auth/register",
    tags=["auth"],
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def auth_register(
    user_data: UserCreate,
    payload: dict = Depends(get_current_user_token_payload),
):
    """Register a new user. Requires authenticated admin."""
    existing = await qafya_adapter.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    password_hash = get_password_hash(user_data.password)
    user_id = str(uuid.uuid4())

    created = await qafya_adapter.create_user(
        user_id=user_id,
        email=user_data.email,
        password_hash=password_hash,
        full_name=user_data.full_name,
        role=user_data.role.value,
        license_no=user_data.license_no,
    )
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="USER_REGISTERED",
        entity_type="user", entity_id=user_id,
        details={"role": user_data.role.value, "registered_by": payload.get("sub")},
    )

    return UserResponse(
        id=user_id, email=user_data.email,
        full_name=user_data.full_name, role=user_data.role,
    )


@router.post("/auth/login", tags=["auth"], response_model=TokenResponse)
async def auth_login(credentials: LoginRequest):
    user = await qafya_adapter.get_user_by_email(credentials.email)
    if not user or not verify_password(credentials.password, user["password_hash"]):
        await qafya_adapter.log_audit(
            user_id=None, action="USER_LOGIN_FAILED",
            entity_type="auth", entity_id=credentials.email,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(
        subject=str(user["id"]),
        role=user["role"],
        facility_id=str(user.get("facility_id", "")),
    )
    refresh_token = create_refresh_token(subject=str(user["id"]))

    await qafya_adapter.log_audit(
        user_id=str(user["id"]), action="USER_LOGIN_SUCCESS",
        entity_type="auth", entity_id=str(user["id"]),
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse(
            id=str(user["id"]), email=credentials.email,
            full_name=user["full_name"], role=UserRole(user["role"]),
        ),
    )


@router.post("/auth/refresh", tags=["auth"], response_model=TokenResponse)
async def auth_refresh(token: str = Depends(oauth2_scheme)) -> TokenResponse:
    """Issue new access+refresh tokens from a valid refresh token.

    Verifies the token type is 'refresh' to prevent access tokens being
    used to mint new tokens (token-type confusion attack).

    @param token: Bearer token extracted via OAuth2 scheme (must be a refresh token).
    @returns: TokenResponse with new access and refresh tokens.
    """
    payload = await verify_refresh_token(token)
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")

    user = await qafya_adapter.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    access_token = create_access_token(
        subject=user_id, role=user["role"],
        facility_id=str(user.get("facility_id", "")),
    )
    refresh_token = create_refresh_token(subject=user_id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/auth/logout", tags=["auth"])
async def auth_logout(payload: dict = Depends(get_current_user_token_payload)):
    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="USER_LOGOUT",
        entity_type="auth", entity_id=payload.get("sub", ""),
    )
    return {"detail": "Logged out successfully"}


@router.get("/auth/profile", tags=["auth"])
async def get_profile(payload: dict = Depends(get_current_user_token_payload)):
    """Get the current user's profile."""
    user = await qafya_adapter.get_user_by_id(payload.get("sub"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "id": str(user["id"]),
        "email": user.get("email", ""),
        "full_name": user["full_name"],
        "role": user["role"],
        "license_no": user.get("license_no"),
        "is_active": user.get("is_active", True),
        "created_at": user.get("created_at"),
    }


@router.put("/auth/profile", tags=["auth"])
async def update_profile(
    payload: dict = Depends(get_current_user_token_payload),
    full_name: str = Body(None),
    license_no: str = Body(None),
):
    """Update the current user's profile (name, license)."""
    user_id = payload.get("sub")
    updates = {}
    if full_name is not None:
        updates["full_name"] = full_name
    if license_no is not None:
        updates["license_no"] = license_no

    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    success = await qafya_adapter.update_user_profile(user_id, updates)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Profile update failed")

    await qafya_adapter.log_audit(
        user_id=user_id, action="PROFILE_UPDATED",
        entity_type="user", entity_id=user_id,
        details={"updated_fields": list(updates.keys())},
    )
    return {"detail": "Profile updated successfully"}


@router.post("/auth/change-password", tags=["auth"])
async def change_password(
    payload: dict = Depends(get_current_user_token_payload),
    current_password: str = Body(...),
    new_password: str = Body(...),
):
    """Change the current user's password."""
    user_id = payload.get("sub")
    user = await qafya_adapter.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(current_password, user["password_hash"]):
        await qafya_adapter.log_audit(
            user_id=user_id, action="PASSWORD_CHANGE_FAILED",
            entity_type="auth", entity_id=user_id,
            details={"reason": "incorrect_current_password"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="New password must be at least 8 characters")

    new_hash = get_password_hash(new_password)
    success = await qafya_adapter.update_user_password(user_id, new_hash)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Password change failed")

    await qafya_adapter.log_audit(
        user_id=user_id, action="PASSWORD_CHANGED",
        entity_type="auth", entity_id=user_id,
    )
    return {"detail": "Password changed successfully"}


# =====================
# PATIENT ENDPOINTS
# =====================
@router.get(
    "/patients/{identifier}",
    tags=["patients"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.BILLING_ADMIN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def get_patient(identifier: str):
    patient = await qafya_adapter.get_patient(identifier)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.get(
    "/patients/{patient_id}/encounters",
    tags=["patients"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.BILLING_ADMIN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def get_patient_encounters(patient_id: str, limit: int = Query(20, ge=1, le=100)):
    return await qafya_adapter.get_patient_encounters(patient_id, limit=limit)


# =====================
# SCRIBE ENDPOINTS
# =====================
@router.post(
    "/scribe/extract",
    tags=["scribe"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def scribe_extract(input_data: TranscriptInput):
    if not input_data.transcript or len(input_data.transcript.strip()) < 10:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transcript too short for meaningful extraction")
    extraction = await nlp_engine.process_transcript(input_data.transcript)
    return extraction


@router.post(
    "/scribe/transcribe",
    tags=["scribe"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def scribe_transcribe(
    audio: UploadFile = File(...),
    token: str = Depends(oauth2_scheme)
):
    """Transcribe audio to text."""
    # Resolve payload manually to avoid 422 conflict with File upload
    payload = await get_current_user_token_payload(token)
    
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only audio files are supported")

    try:
        # Pass (filename, file_body, content_type) to OpenAI
        transcript = await nlp_engine.transcribe((audio.filename, audio.file, audio.content_type))
        
        await qafya_adapter.log_audit(
            user_id=payload.get("sub"), action="AUDIO_TRANSCRIBED",
            entity_type="scribe", entity_id=str(uuid.uuid4()),
            details={"transcript_length": len(transcript), "audio_filename": audio.filename}
        )
        
        return {"transcript": transcript}
    except Exception as e:
        logger.error("scribe_transcribe_failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/scribe/process",
    tags=["scribe"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def scribe_process(input_data: TranscriptInput):
    """Full pipeline: extract + auto-scrub in a single call."""
    if not input_data.transcript or len(input_data.transcript.strip()) < 10:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transcript too short")

    extraction = await nlp_engine.process_transcript(input_data.transcript)
    return {"extraction": extraction, "message": "Extraction complete. Run /claims/scrub to validate."}


@router.post(
    "/scribe/addendum",
    tags=["scribe"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def scribe_addendum(
    encounter_id: str = Body(...),
    addendum_text: str = Body(...),
    payload: dict = Depends(get_current_user_token_payload),
):
    """Append addendum text to an existing encounter's SOAP note."""
    success = await qafya_adapter.append_addendum(encounter_id, addendum_text, payload.get("sub"))
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to append addendum")
    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="ADDENDUM_ADDED",
        entity_type="encounter", entity_id=encounter_id,
        details={"addendum_length": len(addendum_text)},
    )
    return {"detail": "Addendum appended successfully", "encounter_id": encounter_id}


# =====================
# CLAIMS ENDPOINTS
# =====================
@router.post(
    "/claims/scrub",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.BILLING_ADMIN, UserRole.SUPERADMIN]))],
)
async def claims_scrub(req: ScrubRequest):
    result = sha_engine.scrub(
        extraction=req.extraction,
        patient_sha_status=req.sha_status,
        patient_sha_package=req.sha_package,
        amount_billed=req.amount,
        encounter_date=req.encounter_date,
        encounter_type=req.encounter_type,
        has_preauth=req.has_preauth,
    )
    return result


@router.get(
    "/claims",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.BILLING_ADMIN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def list_claims(
    status_filter: str = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    claims = await qafya_adapter.get_claims(status_filter=status_filter, limit=limit, offset=offset)
    total = await qafya_adapter.get_claims_count(status_filter=status_filter)
    return {"claims": claims, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/claims/{claim_id}",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.BILLING_ADMIN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def get_claim(claim_id: str):
    claim = await qafya_adapter.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    return claim


@router.post(
    "/claims/{claim_id}/override",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.BILLING_ADMIN, UserRole.SUPERADMIN]))],
)
async def override_claim(claim_id: str, req: ClaimOverrideRequest, payload: dict = Depends(get_current_user_token_payload)):
    claim = await qafya_adapter.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if claim.get("scrub_status") not in ("blocked", "warnings_only"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only blocked or warning claims can be overridden")

    success = await qafya_adapter.override_claim(
        claim_id=claim_id,
        user_id=payload.get("sub"),
        reason=req.reason,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Override failed")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="CLAIM_OVERRIDE",
        entity_type="claim", entity_id=claim_id,
        details={"reason": req.reason, "previous_status": claim.get("scrub_status")},
    )
    return {"detail": "Claim overridden successfully", "claim_id": claim_id, "new_status": "overridden"}


@router.post(
    "/claims/{claim_id}/submit",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.BILLING_ADMIN, UserRole.SUPERADMIN]))],
)
async def submit_claim(claim_id: str, payload: dict = Depends(get_current_user_token_payload)):
    claim = await qafya_adapter.get_claim_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")

    if claim.get("scrub_status") not in ("passed", "warnings_only", "overridden"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Claim cannot be submitted in current state")

    sha_ref = f"SHA-{uuid.uuid4().hex[:12].upper()}"
    success = await qafya_adapter.submit_claim(claim_id=claim_id, sha_ref=sha_ref)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Submission failed")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="CLAIM_SUBMITTED",
        entity_type="claim", entity_id=claim_id,
        details={"sha_submission_ref": sha_ref},
    )
    return {"detail": "Claim submitted to SHA", "sha_submission_ref": sha_ref}


# =====================
# DISCHARGE ENDPOINTS
# =====================
@router.post(
    "/discharge/generate",
    tags=["discharge"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def generate_discharge(req: DischargeRequest, payload: dict = Depends(get_current_user_token_payload)):
    try:
        summary = await discharge_engine.generate(req.admission_id, req.patient_id)
        summary_id = await qafya_adapter.save_discharge_summary(summary, req.admission_id, req.patient_id, payload.get("sub"))
        summary.id = str(summary_id) if summary_id else None

        await qafya_adapter.log_audit(
            user_id=payload.get("sub"), action="DISCHARGE_GENERATED",
            entity_type="discharge", entity_id=req.admission_id,
        )
        return summary
    except DischargeEngineException as e:
        logger.warning("discharge_generation_clinical_error", error=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("discharge_generation_system_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected system error occurred during synthesis")


@router.get("/discharge/{discharge_id}", tags=["discharge"])
async def get_discharge(discharge_id: str, payload: dict = Depends(get_current_user_token_payload)):
    discharge = await qafya_adapter.get_discharge_by_id(discharge_id)
    if not discharge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")
    return discharge


@router.put(
    "/discharge/{discharge_id}/status",
    tags=["discharge"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def update_discharge_status(
    discharge_id: str,
    req: DischargeStatusUpdate,
    payload: dict = Depends(get_current_user_token_payload),
):
    discharge = await qafya_adapter.get_discharge_by_id(discharge_id)
    if not discharge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")

    current = discharge.get("status", "draft")
    valid_transitions = {
        "draft": ["reviewed"],
        "reviewed": ["approved", "draft"],
        "approved": ["sent_to_qafya"],
    }
    if req.new_status not in valid_transitions.get(current, []):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition: {current} -> {req.new_status}",
        )

    success = await qafya_adapter.update_discharge_status(
        discharge_id=discharge_id,
        new_status=req.new_status,
        user_id=payload.get("sub"),
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Status update failed")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action=f"DISCHARGE_{req.new_status.upper()}",
        entity_type="discharge", entity_id=discharge_id,
        details={"previous_status": current, "new_status": req.new_status},
    )
    return {"detail": "Status updated", "discharge_id": discharge_id, "status": req.new_status}


@router.get("/discharge/{discharge_id}/pdf", tags=["discharge"])
async def download_discharge_pdf(discharge_id: str, payload: dict = Depends(get_current_user_token_payload)):
    discharge = await qafya_adapter.get_discharge_by_id(discharge_id)
    if not discharge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")

    pdf_bytes = discharge_engine.generate_pdf(discharge)

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="DISCHARGE_PDF_DOWNLOADED",
        entity_type="discharge", entity_id=discharge_id,
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=discharge_{discharge_id}.pdf"},
    )


# =====================
# SYNC ENDPOINTS
# =====================
@router.post(
    "/sync/clinical-note",
    tags=["sync"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def sync_clinical_note(req: SyncNoteRequest, payload: dict = Depends(get_current_user_token_payload)):
    res = await qafya_adapter.write_clinical_note(req.qafya_encounter_id, req.soap_json)
    if not res:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sync to Q-Afya failed")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="CLINICAL_NOTE_SYNCED",
        entity_type="encounter", entity_id=req.qafya_encounter_id,
    )
    return {"synced": True, "encounter_id": req.qafya_encounter_id}


@router.post(
    "/sync/discharge-summary",
    tags=["sync"],
    dependencies=[Depends(RoleChecker([UserRole.CLINICIAN, UserRole.SUPERADMIN]))],
)
async def sync_discharge_summary(req: SyncDischargeRequest, payload: dict = Depends(get_current_user_token_payload)):
    discharge = await qafya_adapter.get_discharge_by_id(req.discharge_id)
    if not discharge:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Discharge summary not found")

    if discharge.get("status") != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved discharge summaries can be synced to Q-Afya")

    success = await qafya_adapter.write_discharge_summary(
        admission_id=discharge.get("admission_id", ""),
        summary=discharge,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Sync to Q-Afya failed")

    await qafya_adapter.update_discharge_status(req.discharge_id, "sent_to_qafya", payload.get("sub"))

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="DISCHARGE_SYNCED_TO_QAFYA",
        entity_type="discharge", entity_id=req.discharge_id,
    )
    return {"synced": True, "discharge_id": req.discharge_id}


# =====================
# ADMIN ENDPOINTS
# =====================
@router.get(
    "/admin/users",
    tags=["admin"],
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def admin_users(limit: int = Query(50, ge=1, le=200)):
    users = await qafya_adapter.get_all_users(limit=limit)
    return {"users": users, "total": len(users)}


@router.post(
    "/admin/users",
    tags=["admin"],
    response_model=UserResponse,
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def admin_create_user(user_data: AdminUserCreate, payload: dict = Depends(get_current_user_token_payload)):
    existing = await qafya_adapter.get_user_by_email(user_data.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this email already exists")

    password_hash = get_password_hash(user_data.password)
    user_id = str(uuid.uuid4())

    created = await qafya_adapter.create_user(
        user_id=user_id,
        email=user_data.email,
        password_hash=password_hash,
        full_name=user_data.full_name,
        role=user_data.role.value,
        license_no=user_data.license_no,
    )
    if not created:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action="USER_CREATED_BY_ADMIN",
        entity_type="user", entity_id=user_id,
        details={"role": user_data.role.value, "created_by": payload.get("sub")},
    )

    return UserResponse(id=user_id, email=user_data.email, full_name=user_data.full_name, role=user_data.role)


@router.put(
    "/admin/users/{user_id}/status",
    tags=["admin"],
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def admin_toggle_user_status(
    user_id: str,
    is_active: bool = Body(..., embed=True),
    payload: dict = Depends(get_current_user_token_payload),
):
    """Enable or disable a user account."""
    if user_id == payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own account status")

    target_user = await qafya_adapter.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    success = await qafya_adapter.update_user_profile(user_id, {"is_active": is_active})
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Status update failed")

    action = "USER_ENABLED" if is_active else "USER_DISABLED"
    await qafya_adapter.log_audit(
        user_id=payload.get("sub"), action=action,
        entity_type="user", entity_id=user_id,
        details={"target_user": target_user.get("full_name"), "is_active": is_active},
    )
    return {"detail": f"User {'enabled' if is_active else 'disabled'}", "user_id": user_id, "is_active": is_active}


@router.get(
    "/admin/audit-log",
    tags=["admin"],
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def admin_audit_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action_filter: str = Query(None, alias="action"),
):
    logs = await qafya_adapter.get_audit_logs(limit=limit, offset=offset, action_filter=action_filter)
    return {"logs": logs, "limit": limit, "offset": offset}


@router.get(
    "/admin/sync-status",
    tags=["admin"],
    dependencies=[Depends(RoleChecker([UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def admin_sync_status():
    return {
        "qafya_connection": "connected" if qafya_adapter.pool else "disconnected",
        "circuit_breaker_state": "open" if qafya_adapter.breaker.is_open else "closed",
        "circuit_breaker_failures": qafya_adapter.breaker.failures,
        "last_success_timestamp": qafya_adapter.last_success_timestamp.isoformat() if qafya_adapter.last_success_timestamp else None,
        "current_latency_ms": round(qafya_adapter.current_latency_ms, 2) if qafya_adapter.current_latency_ms else None,
    }


# =====================
# CLAIMS STATS (for billing dashboard)
# =====================
@router.get(
    "/claims/stats",
    tags=["claims"],
    dependencies=[Depends(RoleChecker([UserRole.BILLING_ADMIN, UserRole.FACILITY_ADMIN, UserRole.SUPERADMIN]))],
)
async def claims_stats():
    stats = await qafya_adapter.get_claims_stats()
    return stats


# Mount router
app.include_router(router)
