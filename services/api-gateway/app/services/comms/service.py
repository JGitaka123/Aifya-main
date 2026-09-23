"""Communication service — message sending, template rendering, consent checks."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication import (
    CommunicationPreference as CommunicationPreferenceRow,
    PatientMessage as PatientMessageRow,
)
from app.services.comms.email_provider import EmailProvider, get_email_provider
from app.services.comms.models import (
    BulkMessageRequest,
    CommunicationPreference,
    CommunicationPreferenceUpdate,
    MessageCategory,
    MessageChannel,
    MessageListResponse,
    MessageResponse,
    MessageStatus,
    MessageTemplate,
    MessageTemplateCreate,
    PatientMessage,
    SendMessageRequest,
)
from app.services.comms.sms_provider import SMSProvider, get_sms_provider
from app.services.comms.templates import DEFAULT_TEMPLATES
from app.services.comms.whatsapp_provider import WhatsAppProvider, get_whatsapp_provider

logger = structlog.get_logger(__name__)

# ── Phone Number Normalization ─────────────────────────────────────────────

_KE_MOBILE_RE = re.compile(r"^0([17]\d{8})$")
_KE_PLUS_RE = re.compile(r"^\+254(\d{9})$")
_KE_254_RE = re.compile(r"^254(\d{9})$")


def normalize_kenyan_phone(raw: str) -> str:
    """
    Normalize a Kenyan phone number to E.164 format (+254XXXXXXXXX).

    Handles formats: 07xx, 01xx, 254xxx, +254xxx.

    @param raw: Raw phone number string
    @returns E.164 formatted phone number
    @raises ValueError: If the phone number cannot be normalized
    """
    cleaned = raw.strip().replace(" ", "").replace("-", "")

    # Already E.164
    match = _KE_PLUS_RE.match(cleaned)
    if match:
        return cleaned

    # 254xxxxxxxxx without +
    match = _KE_254_RE.match(cleaned)
    if match:
        return f"+254{match.group(1)}"

    # 07xxxxxxxx or 01xxxxxxxx
    match = _KE_MOBILE_RE.match(cleaned)
    if match:
        return f"+254{match.group(1)}"

    raise ValueError(
        f"Cannot normalize phone number '{raw}'. "
        "Expected Kenyan format: 07xx, 01xx, +254xxx, or 254xxx."
    )


# ── Template Rendering ─────────────────────────────────────────────────────


def render_template(body_template: str, params: dict[str, str]) -> str:
    """
    Render a message template by replacing {placeholder} tokens.

    @param body_template: Template string with {key} placeholders
    @param params: Mapping of placeholder key to value
    @returns Rendered message body
    """
    result = body_template
    for key, value in params.items():
        result = result.replace(f"{{{key}}}", value)
    return result


# ── Delivery Outcome ───────────────────────────────────────────────────────

# Environment variables an operator must set to enable each channel.
_PROVIDER_HINTS: dict[MessageChannel, str] = {
    MessageChannel.sms: "AT_USERNAME and AT_API_KEY (plus a registered AT_SENDER_ID)",
    MessageChannel.whatsapp: (
        "WA_INSTANCE_ID and WA_ACCESS_TOKEN (Green API), or "
        "WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID (Meta Cloud)"
    ),
    MessageChannel.email: "SMTP_HOST and SMTP_FROM_EMAIL",
}

_DEFAULT_SUBJECTS: dict[MessageCategory, str] = {
    MessageCategory.appointment_reminder: "Appointment reminder",
    MessageCategory.lab_result: "Your lab result is ready",
    MessageCategory.prescription_alert: "Prescription update",
    MessageCategory.anc_reminder: "Antenatal care reminder",
    MessageCategory.immunization_reminder: "Immunization reminder",
    MessageCategory.discharge_instructions: "Discharge instructions",
    MessageCategory.follow_up: "Follow-up appointment",
    MessageCategory.billing_notification: "Billing notification",
    MessageCategory.custom: "Message from your health facility",
}


@dataclass(frozen=True)
class DeliveryResult:
    """Outcome of one delivery attempt, carrying a reason when nothing was sent."""

    ok: bool
    detail: str | None = None


def _unconfigured(channel: MessageChannel) -> str:
    """
    Build the operator-facing reason a channel cannot deliver yet.

    @param channel: Channel that was attempted
    @returns Reason naming the environment variables to configure
    """
    hint = _PROVIDER_HINTS.get(channel, "the provider credentials")
    return (
        f"{channel.value.upper()} delivery is not configured on this server. "
        f"Set {hint} to enable it."
    )


def _rejected(channel: MessageChannel, reason: str | None = None) -> str:
    """
    Build the reason a configured provider refused a message.

    @param channel: Channel that was attempted
    @param reason: The provider's own explanation, when it supplied one
    @returns Reason naming the setting worth checking, plus the provider error
    """
    hint = _PROVIDER_HINTS.get(channel, "the provider credentials")
    detail = (
        f"The {channel.value.upper()} provider rejected this message. "
        f"Check {hint}, and that the recipient details are valid."
    )
    if reason:
        return f"{detail} Provider said: {reason}"
    return detail


def _default_subject(category: MessageCategory) -> str:
    """
    Subject line used when the caller does not supply one.

    @param category: Message category
    @returns Human-readable subject
    """
    return _DEFAULT_SUBJECTS.get(category, "Message from your health facility")


# ── Service Class ──────────────────────────────────────────────────────────


class CommunicationService:
    """
    Service for patient communications: sending, template management,
    consent enforcement, and message history.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._sms: SMSProvider = get_sms_provider()
        self._whatsapp: WhatsAppProvider = get_whatsapp_provider()
        self._email: EmailProvider = get_email_provider()

        # Templates stay in memory: the built-in catalogue is re-seeded from
        # DEFAULT_TEMPLATES on every construction. Messages and preferences are
        # persisted, so the send history and the consent record outlive the
        # request that created them.
        self._templates: dict[uuid.UUID, MessageTemplate] = {}
        self._custom_templates: dict[uuid.UUID, MessageTemplate] = {}

        # Seed default templates
        self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Seed in-memory template store from built-in defaults."""
        for dt in DEFAULT_TEMPLATES:
            tid = uuid.uuid5(uuid.NAMESPACE_DNS, dt.name)
            now = datetime.now(UTC)
            self._templates[tid] = MessageTemplate(
                id=tid,
                name=dt.name,
                category=dt.category,
                channel=dt.channel,
                body_template=dt.body_template,
                is_active=True,
                language=dt.language,
                created_at=now,
            )

    # ── Persistence ────────────────────────────────────────────────────────

    async def _store(
        self,
        msg: PatientMessage,
        created_by: uuid.UUID | None = None,
    ) -> None:
        """
        Persist one message so it survives the request that created it.

        @param msg: Message to store
        @param created_by: Staff user who triggered the send, when known
        """
        self.db.add(
            PatientMessageRow(
                id=msg.id,
                facility_id=msg.facility_id,
                patient_id=msg.patient_id,
                channel=msg.channel.value,
                category=msg.category.value,
                recipient_phone=msg.recipient_phone,
                recipient_email=msg.recipient_email,
                subject=msg.subject,
                template_id=msg.template_id,
                template_params=msg.template_params,
                body=msg.body,
                status=msg.status.value,
                retry_count=msg.retry_count,
                scheduled_at=msg.scheduled_at,
                sent_at=msg.sent_at,
                error_message=msg.error_message,
                created_at=msg.created_at,
                created_by=created_by,
                updated_by=created_by,
            )
        )
        await self.db.flush()

    @staticmethod
    def _to_message(row: PatientMessageRow) -> PatientMessage:
        """
        Convert a stored row back into the service model.

        @param row: Database row
        @returns PatientMessage
        """
        return PatientMessage(
            id=row.id,
            patient_id=row.patient_id,
            facility_id=row.facility_id,
            channel=MessageChannel(row.channel),
            category=MessageCategory(row.category),
            recipient_phone=row.recipient_phone,
            recipient_email=row.recipient_email,
            subject=row.subject,
            template_id=row.template_id,
            template_params=row.template_params,
            body=row.body,
            status=MessageStatus(row.status),
            retry_count=row.retry_count,
            scheduled_at=row.scheduled_at,
            sent_at=row.sent_at,
            delivered_at=row.delivered_at,
            read_at=row.read_at,
            error_message=row.error_message,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_response(row: PatientMessageRow) -> MessageResponse:
        """
        Convert a stored row into the history/detail response model.

        @param row: Database row
        @returns MessageResponse
        """
        return MessageResponse(
            id=row.id,
            patient_id=row.patient_id,
            facility_id=row.facility_id,
            channel=MessageChannel(row.channel),
            category=MessageCategory(row.category),
            recipient_phone=row.recipient_phone,
            recipient_email=row.recipient_email,
            subject=row.subject,
            template_id=row.template_id,
            body=row.body,
            status=MessageStatus(row.status),
            retry_count=row.retry_count,
            sent_at=row.sent_at,
            delivered_at=row.delivered_at,
            read_at=row.read_at,
            error_message=row.error_message,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_preference(row: CommunicationPreferenceRow) -> CommunicationPreference:
        """
        Convert a stored consent record into the response model.

        @param row: Database row
        @returns CommunicationPreference
        """
        return CommunicationPreference(
            id=row.id,
            patient_id=row.patient_id,
            facility_id=row.facility_id,
            preferred_channel=MessageChannel(row.preferred_channel),
            opt_out_categories=[
                MessageCategory(c) for c in (row.opt_out_categories or [])
            ],
            consent_given=row.consent_given,
            consent_date=row.consent_date,
            preferred_language=row.preferred_language,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    # ── Consent ────────────────────────────────────────────────────────────

    async def _check_consent(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        category: MessageCategory,
    ) -> bool:
        """
        Check if the patient has given consent and has not opted out of this
        message category. Required by Kenya Data Protection Act.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param category: Message category to check
        @returns True if the message may be sent
        """
        result = await self.db.execute(
            select(CommunicationPreferenceRow).where(
                CommunicationPreferenceRow.patient_id == patient_id,
                CommunicationPreferenceRow.facility_id == facility_id,
                CommunicationPreferenceRow.is_deleted == False,  # noqa: E712
            )
        )
        pref = result.scalar_one_or_none()
        if pref is None:
            # No preferences stored — default to allowing (facility can
            # set consent during registration).
            return True
        if not pref.consent_given:
            logger.warning(
                "message_blocked_no_consent",
                patient_id=str(patient_id),
                category=category,
            )
            return False
        if category.value in (pref.opt_out_categories or []):
            logger.info(
                "message_blocked_opt_out",
                patient_id=str(patient_id),
                category=category,
            )
            return False
        return True

    # ── Send ───────────────────────────────────────────────────────────────

    async def send_message(
        self,
        facility_id: uuid.UUID,
        request: SendMessageRequest,
        recipient_phone: str = "",
        recipient_email: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> PatientMessage:
        """
        Send a single message to a patient.

        @param facility_id: Facility UUID from JWT
        @param request: Send message request data
        @param recipient_phone: Raw patient phone number (SMS / WhatsApp)
        @param recipient_email: Patient email address (email channel)
        @param created_by: Staff user who triggered the send, when known
        @returns Created PatientMessage with delivery status
        @raises ValueError: If consent not given or the recipient is unusable
        """
        # Consent check (Kenya DPA)
        if not await self._check_consent(
            request.patient_id, facility_id, request.category
        ):
            raise ValueError(
                "Patient has not given communication consent or has opted out "
                "of this message category."
            )

        # Only the dialling channels need a phone number; email does not.
        needs_phone = request.channel in (
            MessageChannel.sms,
            MessageChannel.whatsapp,
        )
        if needs_phone and not recipient_phone:
            raise ValueError("This channel needs the patient's phone number.")

        # Normalize phone
        normalized_phone = (
            normalize_kenyan_phone(recipient_phone) if needs_phone else ""
        )

        subject = request.subject or _default_subject(request.category)

        # Resolve body
        body: str
        if request.template_id and request.template_id in self._templates:
            template = self._templates[request.template_id]
            params = request.template_params or {}
            body = render_template(template.body_template, params)
        elif request.template_id and request.template_id in self._custom_templates:
            template = self._custom_templates[request.template_id]
            params = request.template_params or {}
            body = render_template(template.body_template, params)
        elif request.body:
            body = request.body
        else:
            raise ValueError(
                "Either template_id with params or body must be provided."
            )

        now = datetime.now(UTC)
        msg_id = uuid.uuid4()

        # Scheduled messages are queued for later
        if request.scheduled_at and request.scheduled_at > now:
            msg = PatientMessage(
                id=msg_id,
                patient_id=request.patient_id,
                facility_id=facility_id,
                channel=request.channel,
                category=request.category,
                recipient_phone=normalized_phone,
                recipient_email=recipient_email,
                subject=subject,
                template_id=request.template_id,
                template_params=request.template_params,
                body=body,
                status=MessageStatus.queued,
                scheduled_at=request.scheduled_at,
                created_at=now,
            )
            await self._store(msg, created_by)
            logger.info(
                "message_scheduled",
                message_id=str(msg_id),
                scheduled_at=request.scheduled_at.isoformat(),
            )
            return msg

        # Deliver immediately
        outcome = await self._deliver(
            request.channel,
            body=body,
            phone=normalized_phone,
            email=recipient_email,
            subject=subject,
        )

        msg = PatientMessage(
            id=msg_id,
            patient_id=request.patient_id,
            facility_id=facility_id,
            channel=request.channel,
            category=request.category,
            recipient_phone=normalized_phone,
            recipient_email=recipient_email,
            subject=subject,
            template_id=request.template_id,
            template_params=request.template_params,
            body=body,
            status=MessageStatus.sent if outcome.ok else MessageStatus.failed,
            sent_at=now if outcome.ok else None,
            error_message=None if outcome.ok else outcome.detail,
            created_at=now,
        )
        await self._store(msg, created_by)
        return msg

    async def send_bulk_messages(
        self,
        facility_id: uuid.UUID,
        request: BulkMessageRequest,
    ) -> list[PatientMessage]:
        """
        Send bulk messages to multiple patients.

        @param facility_id: Facility UUID from JWT
        @param request: Bulk message request
        @returns List of created PatientMessage records
        """
        patient_ids = request.patient_ids or []
        results: list[PatientMessage] = []

        for pid in patient_ids:
            SendMessageRequest(
                patient_id=pid,
                channel=request.channel,
                category=request.category,
                template_id=request.template_id,
                template_params=request.template_params,
            )
            try:
                # In production, look up the patient phone from DB.
                # For now we skip patients without a known phone.
                logger.info(
                    "bulk_message_queued",
                    patient_id=str(pid),
                    category=request.category,
                )
                now = datetime.now(UTC)
                msg = PatientMessage(
                    id=uuid.uuid4(),
                    patient_id=pid,
                    facility_id=facility_id,
                    channel=request.channel,
                    category=request.category,
                    recipient_phone="pending_lookup",
                    template_id=request.template_id,
                    template_params=request.template_params,
                    body="(pending template render)",
                    status=MessageStatus.queued,
                    created_at=now,
                )
                await self._store(msg)
                results.append(msg)
            except ValueError as exc:
                logger.warning(
                    "bulk_message_skipped",
                    patient_id=str(pid),
                    reason=str(exc),
                )

        return results

    async def _deliver(
        self,
        channel: MessageChannel,
        *,
        body: str,
        phone: str = "",
        email: str | None = None,
        subject: str | None = None,
    ) -> DeliveryResult:
        """
        Dispatch a message through the appropriate channel provider.

        A channel whose provider credentials are missing reports a precise
        reason rather than a false success, so the operator can tell the
        difference between "delivered" and "never left the server".

        @param channel: Target channel (sms / whatsapp / email)
        @param body: Message body text
        @param phone: E.164 phone number, for SMS and WhatsApp
        @param email: Recipient address, for email
        @param subject: Subject line, for email
        @returns DeliveryResult with the outcome and a reason when unsent
        """
        if channel == MessageChannel.sms:
            if not self._sms.is_configured:
                return DeliveryResult(ok=False, detail=_unconfigured(channel))
            if await self._sms.send_sms(phone, body):
                return DeliveryResult(ok=True)
            return DeliveryResult(
                ok=False, detail=_rejected(channel, self._sms.last_error)
            )

        if channel == MessageChannel.whatsapp:
            if not self._whatsapp.is_configured:
                return DeliveryResult(ok=False, detail=_unconfigured(channel))
            if await self._whatsapp.send_message(phone, body):
                return DeliveryResult(ok=True)
            return DeliveryResult(
                ok=False,
                detail=_rejected(channel, self._whatsapp.last_error),
            )

        if channel == MessageChannel.email:
            if not email:
                return DeliveryResult(
                    ok=False,
                    detail="This patient has no email address on file.",
                )
            if not self._email.is_configured:
                return DeliveryResult(ok=False, detail=_unconfigured(channel))
            if await self._email.send_email(
                email,
                subject or _default_subject(MessageCategory.custom),
                body,
            ):
                return DeliveryResult(ok=True)
            return DeliveryResult(
                ok=False, detail=_rejected(channel, self._email.last_error)
            )

        return DeliveryResult(
            ok=False, detail=f"Unsupported channel '{channel}'."
        )

    # ── Message History ────────────────────────────────────────────────────

    async def get_message_history(
        self,
        facility_id: uuid.UUID,
        *,
        patient_id: uuid.UUID | None = None,
        page: int = 1,
        per_page: int = 20,
        status: MessageStatus | None = None,
        channel: MessageChannel | None = None,
    ) -> MessageListResponse:
        """
        Retrieve paginated message history for a facility.

        @param facility_id: Facility UUID
        @param patient_id: Optional patient filter
        @param page: Page number (1-based)
        @param per_page: Items per page
        @param status: Optional status filter
        @param channel: Optional channel filter
        @returns Paginated message list
        """
        filters = [
            PatientMessageRow.facility_id == facility_id,
            PatientMessageRow.is_deleted == False,  # noqa: E712
        ]
        if patient_id is not None:
            filters.append(PatientMessageRow.patient_id == patient_id)
        if status is not None:
            filters.append(PatientMessageRow.status == status.value)
        if channel is not None:
            filters.append(PatientMessageRow.channel == channel.value)

        total = await self.db.scalar(
            select(func.count()).select_from(PatientMessageRow).where(*filters)
        )
        result = await self.db.execute(
            select(PatientMessageRow)
            .where(*filters)
            .order_by(PatientMessageRow.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )

        return MessageListResponse(
            items=[self._to_response(row) for row in result.scalars().all()],
            total=total or 0,
            page=page,
            per_page=per_page,
        )

    async def get_message_detail(
        self,
        facility_id: uuid.UUID,
        message_id: uuid.UUID,
    ) -> MessageResponse | None:
        """
        Retrieve a single message by ID, scoped to facility.

        @param facility_id: Facility UUID
        @param message_id: Message UUID
        @returns MessageResponse or None if not found
        """
        result = await self.db.execute(
            select(PatientMessageRow).where(
                PatientMessageRow.id == message_id,
                PatientMessageRow.facility_id == facility_id,
                PatientMessageRow.is_deleted == False,  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_response(row)

    # ── Preferences ────────────────────────────────────────────────────────

    async def get_patient_preferences(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> CommunicationPreference:
        """
        Get communication preferences for a patient. Creates defaults if none exist.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @returns CommunicationPreference record
        """
        result = await self.db.execute(
            select(CommunicationPreferenceRow).where(
                CommunicationPreferenceRow.patient_id == patient_id,
                CommunicationPreferenceRow.facility_id == facility_id,
                CommunicationPreferenceRow.is_deleted == False,  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            now = datetime.now(UTC)
            row = CommunicationPreferenceRow(
                id=uuid.uuid4(),
                patient_id=patient_id,
                facility_id=facility_id,
                preferred_channel=MessageChannel.sms.value,
                opt_out_categories=[],
                consent_given=False,
                consent_date=None,
                preferred_language="en",
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
            await self.db.flush()
        return self._to_preference(row)

    async def update_patient_preferences(
        self,
        patient_id: uuid.UUID,
        facility_id: uuid.UUID,
        data: CommunicationPreferenceUpdate,
    ) -> CommunicationPreference:
        """
        Update communication preferences for a patient.

        @param patient_id: Patient UUID
        @param facility_id: Facility UUID
        @param data: Fields to update
        @returns Updated CommunicationPreference
        """
        await self.get_patient_preferences(patient_id, facility_id)

        result = await self.db.execute(
            select(CommunicationPreferenceRow).where(
                CommunicationPreferenceRow.patient_id == patient_id,
                CommunicationPreferenceRow.facility_id == facility_id,
                CommunicationPreferenceRow.is_deleted == False,  # noqa: E712
            )
        )
        row = result.scalar_one()
        now = datetime.now(UTC)

        if data.preferred_channel is not None:
            row.preferred_channel = data.preferred_channel.value
        if data.opt_out_categories is not None:
            row.opt_out_categories = [c.value for c in data.opt_out_categories]
        if data.consent_given is not None:
            row.consent_given = data.consent_given
            if data.consent_given:
                row.consent_date = now
        if data.preferred_language is not None:
            row.preferred_language = data.preferred_language
        row.updated_at = now

        await self.db.flush()
        return self._to_preference(row)

    # ── Templates ──────────────────────────────────────────────────────────

    async def list_templates(
        self,
        *,
        language: str | None = None,
        channel: MessageChannel | None = None,
        category: MessageCategory | None = None,
    ) -> list[MessageTemplate]:
        """
        List all available message templates (default + custom).

        @param language: Optional language filter
        @param channel: Optional channel filter
        @param category: Optional category filter
        @returns List of MessageTemplate
        """
        all_templates = list(self._templates.values()) + list(
            self._custom_templates.values()
        )
        if language:
            all_templates = [t for t in all_templates if t.language == language]
        if channel:
            all_templates = [t for t in all_templates if t.channel == channel]
        if category:
            all_templates = [t for t in all_templates if t.category == category]
        return [t for t in all_templates if t.is_active]

    async def create_template(
        self,
        facility_id: uuid.UUID,
        data: MessageTemplateCreate,
    ) -> MessageTemplate:
        """
        Create a custom message template.

        @param facility_id: Facility UUID (for scoping)
        @param data: Template creation data
        @returns Created MessageTemplate
        """
        now = datetime.now(UTC)
        tid = uuid.uuid4()
        template = MessageTemplate(
            id=tid,
            name=data.name,
            category=data.category,
            channel=data.channel,
            body_template=data.body_template,
            is_active=True,
            language=data.language,
            created_at=now,
        )
        self._custom_templates[tid] = template
        logger.info(
            "template_created",
            template_id=str(tid),
            name=data.name,
            facility_id=str(facility_id),
        )
        return template

    # ── Retry ──────────────────────────────────────────────────────────────

    async def retry_failed_messages(self, max_retries: int = 3) -> int:
        """
        Retry delivery of failed/queued messages up to max_retries.

        @param max_retries: Maximum retry attempts per message
        @returns Number of messages successfully retried
        """
        result = await self.db.execute(
            select(PatientMessageRow).where(
                PatientMessageRow.status.in_(
                    [MessageStatus.failed.value, MessageStatus.queued.value]
                ),
                PatientMessageRow.retry_count < max_retries,
                PatientMessageRow.is_deleted == False,  # noqa: E712
            )
        )
        rows = result.scalars().all()

        retried = 0
        for row in rows:
            msg = self._to_message(row)
            outcome = await self._deliver(
                msg.channel,
                body=msg.body,
                phone=msg.recipient_phone,
                email=msg.recipient_email,
                subject=msg.subject,
            )
            now = datetime.now(UTC)

            row.retry_count = msg.retry_count + 1
            row.updated_at = now
            if outcome.ok:
                row.status = MessageStatus.sent.value
                row.sent_at = now
                row.error_message = None
                retried += 1
            else:
                row.error_message = (
                    outcome.detail or f"Retry {msg.retry_count + 1} failed"
                )

        if rows:
            await self.db.flush()

        return retried
