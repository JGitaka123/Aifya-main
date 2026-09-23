"""Default message templates for the Patient Communication Hub (EN + SW)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.comms.models import MessageCategory, MessageChannel


@dataclass(frozen=True)
class DefaultTemplate:
    """A built-in message template definition."""

    name: str
    category: MessageCategory
    channel: MessageChannel
    language: str
    body_template: str


# ── English Templates ──────────────────────────────────────────────────────

_EN_APPOINTMENT_REMINDER = DefaultTemplate(
    name="appointment_reminder_en",
    category=MessageCategory.appointment_reminder,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, this is a reminder of your appointment at "
        "{facility_name} on {date} at {time}. Reply CONFIRM to confirm or "
        "CANCEL to cancel."
    ),
)

_EN_LAB_RESULT = DefaultTemplate(
    name="lab_result_ready_en",
    category=MessageCategory.lab_result,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, your lab results for {test_name} are ready. "
        "Please visit {facility_name} to collect your results."
    ),
)

_EN_PRESCRIPTION_ALERT = DefaultTemplate(
    name="prescription_ready_en",
    category=MessageCategory.prescription_alert,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, your prescription is ready for collection at "
        "{facility_name} pharmacy."
    ),
)

_EN_ANC_REMINDER = DefaultTemplate(
    name="anc_visit_reminder_en",
    category=MessageCategory.anc_reminder,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, your next ANC visit is on {date}. "
        "Please bring your ANC booklet."
    ),
)

_EN_IMMUNIZATION_REMINDER = DefaultTemplate(
    name="immunization_reminder_en",
    category=MessageCategory.immunization_reminder,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, {child_name}'s {vaccine_name} vaccination is "
        "due on {date} at {facility_name}."
    ),
)

_EN_FOLLOW_UP = DefaultTemplate(
    name="follow_up_reminder_en",
    category=MessageCategory.follow_up,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, you have a follow-up appointment on {date} "
        "at {facility_name}."
    ),
)

_EN_DISCHARGE = DefaultTemplate(
    name="discharge_instructions_en",
    category=MessageCategory.discharge_instructions,
    channel=MessageChannel.sms,
    language="en",
    body_template=(
        "Dear {patient_name}, thank you for visiting {facility_name}. "
        "Please follow your discharge instructions. Call {facility_phone} "
        "if you have concerns."
    ),
)

# ── Swahili Templates ─────────────────────────────────────────────────────

_SW_APPOINTMENT_REMINDER = DefaultTemplate(
    name="appointment_reminder_sw",
    category=MessageCategory.appointment_reminder,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, hii ni ukumbusho wa miadi yako katika "
        "{facility_name} tarehe {date} saa {time}. Jibu THIBITISHA kuthibitisha "
        "au GHAIRI kughairi."
    ),
)

_SW_LAB_RESULT = DefaultTemplate(
    name="lab_result_ready_sw",
    category=MessageCategory.lab_result,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, matokeo yako ya maabara ya {test_name} "
        "yako tayari. Tafadhali tembelea {facility_name} kuchukua matokeo yako."
    ),
)

_SW_PRESCRIPTION_ALERT = DefaultTemplate(
    name="prescription_ready_sw",
    category=MessageCategory.prescription_alert,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, dawa yako iko tayari kuchukuliwa katika "
        "famasi ya {facility_name}."
    ),
)

_SW_ANC_REMINDER = DefaultTemplate(
    name="anc_visit_reminder_sw",
    category=MessageCategory.anc_reminder,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, miadi yako ya kliniki ya wajawazito ni "
        "tarehe {date}. Tafadhali kuja na kitabu chako cha ANC."
    ),
)

_SW_IMMUNIZATION_REMINDER = DefaultTemplate(
    name="immunization_reminder_sw",
    category=MessageCategory.immunization_reminder,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, chanjo ya {vaccine_name} ya {child_name} "
        "inapaswa kufanywa tarehe {date} katika {facility_name}."
    ),
)

_SW_FOLLOW_UP = DefaultTemplate(
    name="follow_up_reminder_sw",
    category=MessageCategory.follow_up,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, una miadi ya kurudi tarehe {date} katika "
        "{facility_name}."
    ),
)

_SW_DISCHARGE = DefaultTemplate(
    name="discharge_instructions_sw",
    category=MessageCategory.discharge_instructions,
    channel=MessageChannel.sms,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, asante kwa kutembelea {facility_name}. "
        "Tafadhali fuata maagizo yako ya kutoka. Piga simu {facility_phone} "
        "ukiwa na wasiwasi."
    ),
)

# ── WhatsApp English Templates ─────────────────────────────────────────────

_EN_APPOINTMENT_REMINDER_WA = DefaultTemplate(
    name="appointment_reminder_wa_en",
    category=MessageCategory.appointment_reminder,
    channel=MessageChannel.whatsapp,
    language="en",
    body_template=(
        "Dear {patient_name}, this is a reminder of your appointment at "
        "{facility_name} on {date} at {time}. Reply CONFIRM to confirm or "
        "CANCEL to cancel."
    ),
)

_EN_LAB_RESULT_WA = DefaultTemplate(
    name="lab_result_ready_wa_en",
    category=MessageCategory.lab_result,
    channel=MessageChannel.whatsapp,
    language="en",
    body_template=(
        "Dear {patient_name}, your lab results for {test_name} are ready. "
        "Please visit {facility_name} to collect your results."
    ),
)

# ── WhatsApp Swahili Templates ─────────────────────────────────────────────

_SW_APPOINTMENT_REMINDER_WA = DefaultTemplate(
    name="appointment_reminder_wa_sw",
    category=MessageCategory.appointment_reminder,
    channel=MessageChannel.whatsapp,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, hii ni ukumbusho wa miadi yako katika "
        "{facility_name} tarehe {date} saa {time}. Jibu THIBITISHA kuthibitisha "
        "au GHAIRI kughairi."
    ),
)

_SW_LAB_RESULT_WA = DefaultTemplate(
    name="lab_result_ready_wa_sw",
    category=MessageCategory.lab_result,
    channel=MessageChannel.whatsapp,
    language="sw",
    body_template=(
        "Mpendwa {patient_name}, matokeo yako ya maabara ya {test_name} "
        "yako tayari. Tafadhali tembelea {facility_name} kuchukua matokeo yako."
    ),
)


# ── Registry ───────────────────────────────────────────────────────────────

DEFAULT_TEMPLATES: list[DefaultTemplate] = [
    # SMS — English
    _EN_APPOINTMENT_REMINDER,
    _EN_LAB_RESULT,
    _EN_PRESCRIPTION_ALERT,
    _EN_ANC_REMINDER,
    _EN_IMMUNIZATION_REMINDER,
    _EN_FOLLOW_UP,
    _EN_DISCHARGE,
    # SMS — Swahili
    _SW_APPOINTMENT_REMINDER,
    _SW_LAB_RESULT,
    _SW_PRESCRIPTION_ALERT,
    _SW_ANC_REMINDER,
    _SW_IMMUNIZATION_REMINDER,
    _SW_FOLLOW_UP,
    _SW_DISCHARGE,
    # WhatsApp — English
    _EN_APPOINTMENT_REMINDER_WA,
    _EN_LAB_RESULT_WA,
    # WhatsApp — Swahili
    _SW_APPOINTMENT_REMINDER_WA,
    _SW_LAB_RESULT_WA,
]


def get_default_templates(
    *,
    language: str | None = None,
    channel: MessageChannel | None = None,
    category: MessageCategory | None = None,
) -> list[DefaultTemplate]:
    """
    Return filtered list of built-in message templates.

    @param language: Filter by ISO 639-1 code (en / sw)
    @param channel: Filter by message channel
    @param category: Filter by message category
    @returns Matching default templates
    """
    result = DEFAULT_TEMPLATES
    if language is not None:
        result = [t for t in result if t.language == language]
    if channel is not None:
        result = [t for t in result if t.channel == channel]
    if category is not None:
        result = [t for t in result if t.category == category]
    return result
