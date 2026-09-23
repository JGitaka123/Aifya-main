"""
Aifya in-app AI help bot ("Aifya Care").
Answers navigation and how-do-I questions about Aifya itself.

Generation prefers DeepSeek (DEEPSEEK_API_KEY) so the assistant works without
the local AI stack; when no key is configured it falls back to the central
ai-service OpenAI-compatible endpoint (AI_SERVICE_URL).

Clinical questions and anything that looks like patient identifiers are
refused before the model is ever called.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Final

import httpx
from pydantic import BaseModel
from structlog import get_logger

from app.config import settings

logger = get_logger(__name__)

_AI_SERVICE_URL: Final[str] = os.getenv("AI_SERVICE_URL", "http://ai-service:8001")

# Canonical in-app destinations the assistant may point users at.
# Mirrors NAV_ITEMS in apps/web/src/lib/navigation.ts - keep the two in
# step, because a wrong href here sends the user to a page that does not
# exist, and a missing one makes the model invent a location.
_MODULE_KEYWORDS: Final[tuple[tuple[str, str, tuple[str, ...]], ...]] = (
    (
        "/user-guide",
        "User Guide",
        (
            "user guide", "user manual", "training", "tutorial", "course",
            "learn", "onboarding", "getting started",
        ),
    ),
    (
        "/knowledge",
        "Knowledge Base",
        (
            "knowledge", "knowledge base", "sop", "sops", "policy",
            "policies", "guideline", "guidelines", "protocol",
            "protocols", "document", "documents", "upload document",
            "upload a document", "institutional knowledge",
            "institutional document",
        ),
    ),
    (
        "/patients/register",
        "Register Patient",
        (
            "register patient", "register a patient", "new patient",
            "add patient", "add a patient", "registration",
        ),
    ),
    (
        "/patients",
        "Patients",
        (
            "patient", "patients", "demographics", "medical record",
        ),
    ),
    (
        "/appointments",
        "Appointments",
        (
            "appointment", "appointments", "booking", "schedule",
            "calendar",
        ),
    ),
    (
        "/referrals",
        "Referrals",
        (
            "referral", "referrals", "incoming referral",
            "outgoing referral",
        ),
    ),
    (
        "/opd",
        "OPD",
        (
            "opd", "outpatient", "out-patient", "consultation",
            "clinic visit",
        ),
    ),
    (
        "/ipd",
        "IPD",
        (
            "ipd", "inpatient", "in-patient", "admission", "admit", "ward",
            "bed", "discharge",
        ),
    ),
    (
        "/emergency",
        "Emergency",
        (
            "emergency", "casualty", "triage",
        ),
    ),
    (
        "/pharmacy",
        "Pharmacy",
        (
            "pharmacy", "dispense", "dispensing", "drug", "drugs",
            "medication", "medicine", "prescription",
        ),
    ),
    (
        "/laboratory",
        "Laboratory",
        (
            "laboratory", "lab", "labs", "lab order", "lab result",
            "lab results", "specimen",
        ),
    ),
    (
        "/radiology",
        "Radiology",
        (
            "radiology", "x-ray", "xray", "mri", "ultrasound", "imaging",
            "scan",
        ),
    ),
    (
        "/theatre",
        "Theatre",
        (
            "theatre", "theater", "surgery", "operation",
            "operating theatre",
        ),
    ),
    (
        "/dental",
        "Dental",
        (
            "dental", "tooth", "teeth", "odontogram",
        ),
    ),
    (
        "/mch",
        "MCH",
        (
            "mch", "anc", "antenatal", "immunization", "immunisation",
            "vaccine", "child health",
        ),
    ),
    (
        "/billing",
        "Billing",
        (
            "bill", "billing", "invoice", "payment", "receipt", "charge",
        ),
    ),
    (
        "/insurance",
        "Insurance",
        (
            "insurance", "sha", "claim", "claims", "preauth", "pre-auth",
            "pre-authorization",
        ),
    ),
    (
        "/finance",
        "Finance",
        (
            "finance", "ledger", "expense", "revenue", "trial balance",
            "p&l", "pnl",
        ),
    ),
    (
        "/finance/payroll",
        "Payroll",
        (
            "payroll", "salary", "salaries", "payslip", "paye", "nssf",
            "shif",
        ),
    ),
    (
        "/hr",
        "HR",
        (
            "hr", "human resource", "human resources", "staff", "employee",
            "employees", "leave", "attendance", "shift",
        ),
    ),
    (
        "/inventory",
        "Inventory",
        (
            "inventory", "stock", "supplier", "purchase order", "store",
        ),
    ),
    (
        "/reports",
        "Reports",
        (
            "report", "reports", "dhis2", "statistics",
        ),
    ),
    (
        "/analytics",
        "Analytics",
        (
            "analytics", "kpi", "kpis", "metrics", "performance",
            "dashboard",
        ),
    ),
    (
        "/communications",
        "Communications",
        (
            "communication", "communications", "sms", "whatsapp", "email",
            "message", "notify", "notification",
        ),
    ),
    (
        "/integrations/fhir",
        "Integrations",
        (
            "integration", "integrations", "fhir", "api",
            "interoperability",
        ),
    ),
    (
        "/trials",
        "Clinical Trials",
        (
            "trial", "trials", "clinical trial", "research",
        ),
    ),
    (
        "/settings",
        "Settings",
        (
            "settings", "configuration", "configure", "facility profile",
        ),
    ),
)

# Word-boundary matcher per keyword. Plain substring matching used to send
# users to Emergency for "us(er )guide" and "regist(er )a", so keywords may
# only match whole words.
_KEYWORD_PATTERNS: Final[dict[str, re.Pattern[str]]] = {
    keyword: re.compile(
        r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE
    )
    for _href, _label, _keywords in _MODULE_KEYWORDS
    for keyword in _keywords
}


def _navigation_catalogue() -> str:
    """
    Render the destinations the assistant is allowed to reference.

    @returns Newline-separated "Label (/href)" lines
    """
    return "\n".join(
        f"- {label} ({href})" for href, label, _keywords in _MODULE_KEYWORDS
    )


_SYSTEM_PROMPT: Final[str] = (
    "You are Aifya Care, the friendly in-app assistant for Aifya, a Kenyan "
    "hospital management system used by hospitals, clinics and health "
    "centres. Be warm and approachable: greet users, tell a light-hearted "
    "joke when asked, and explain everyday topics or general health "
    "education in simple language. Your main job is helping with Aifya "
    "itself: how to use the system, navigate modules, register patients, "
    "and work with billing, pharmacy, laboratory, appointments and "
    "reports. Be concise (max 4 short paragraphs). "
    "If asked clinical questions (drug doses, diagnosis, treatment), do "
    "NOT answer - instead politely redirect the user to the clinician or "
    "to the Clinical Decision Support module. "
    "When you suggest a feature, name the module exactly as it appears in "
    "the navigation list below. "
    "These are the only screens that exist. Never invent a path, a menu "
    "item or a location, and never send the user somewhere that is not on "
    "this list:\n"
    + _navigation_catalogue()
    + "\nTwo locations users ask about most: the help assistant itself is "
    "the round sparkle button fixed at the BOTTOM-RIGHT of every screen - "
    "it is never in the top bar, and there is no separate help icon in the "
    "top-right. The User Guide is its own sidebar item named 'User Guide' "
    "with a graduation-cap icon; it is not inside Settings."
)


class SuggestedLink(BaseModel):
    """A suggested in-app navigation link returned to the UI."""

    label: str
    href: str


class AnswerResponse(BaseModel):
    """
    Help bot answer.

    @param answer: Free-text answer
    @param suggested_links: In-app routes the user might want to open
    @param confidence: 0-1 self-reported confidence (heuristic)
    @param model: Backing model name
    """

    answer: str
    suggested_links: list[SuggestedLink] = []
    confidence: float = 0.5
    model: str = "unknown"


def _suggest_links(query: str) -> list[SuggestedLink]:
    """
    Suggest navigation links for a question using whole-word matching.

    Ranked by matched keyword length, so a phrase such as "user guide"
    outranks an incidental single-word hit.

    @param query: User question
    @returns Up to 3 suggested links, most specific first
    """
    haystack = query.casefold()
    scored: list[tuple[int, int, str, str]] = []
    for order, (href, label, keywords) in enumerate(_MODULE_KEYWORDS):
        strongest = 0
        for keyword in keywords:
            if _KEYWORD_PATTERNS[keyword].search(haystack):
                strongest = max(strongest, len(keyword))
        if strongest:
            scored.append((strongest, -order, href, label))

    scored.sort(reverse=True)
    return [
        SuggestedLink(label=label, href=href)
        for _score, _order, href, label in scored[:3]
    ]

_CLINICAL_RED_FLAGS = re.compile(
    r"\b(dose|dosage|dosing|treat|treatment|prescribe|prescription|"
    r"diagnos|differential|interaction|contraindicat|antibiotic|"
    r"chemo|chemotherapy|insulin|warfarin|paracetamol|amoxicillin|"
    r"morphine|fentanyl|codeine|"
    r"should\s+i\s+(prescribe|give|order|recommend|treat|administer)|"
    r"what\s+(dose|dosage|drug|medication|medicine|antibiotic)|"
    r"how\s+much\s+(\w+\s+){0,3}(give|prescribe|administer)|"
    r"is\s+it\s+safe\s+to\s+(give|use|combine)|"
    r"can\s+i\s+(give|prescribe|combine|stop)|"
    r"side\s+effect|adverse\s+effect|drug\s+interaction)\b",
    re.IGNORECASE,
)

# PHI red flags: identifiers that suggest the query carries patient data.
_PHI_RED_FLAGS = re.compile(
    r"\b("
    r"\d{6,}"  # long numeric (likely MRN / phone / ID)
    r"|MRN[:\s-]*\w+"
    r"|patient[\s_-]*id[:\s=]*\w+"
    r"|kra[\s_-]*pin[:\s=]*\w+"
    r"|nssf[\s_-]*\w+"
    r"|shif[\s_-]*\w+"
    r"|@\w+\.\w+"  # email address
    r")",
    re.IGNORECASE,
)


async def answer_help_query(
    query: str,
    user_role: str = "staff",
    facility_id: uuid.UUID | None = None,
    context: str | None = None,
) -> AnswerResponse:
    """
    Answer a help / how-do-I query via the AI service.

    @param query: The user question
    @param user_role: Role hint for the LLM (e.g. "doctor", "nurse")
    @param facility_id: Tenant facility UUID (for telemetry)
    @param context: Screen the user is on, e.g. "/user-guide" (optional)
    @returns AnswerResponse
    """
    suggested = _suggest_links(query)

    # Hard guardrail: never answer clinical questions through the help bot
    if _CLINICAL_RED_FLAGS.search(query):
        # NOTE: do NOT include the query content in logs — may contain PHI
        logger.info(
            "help_bot_clinical_blocked",
            facility_id=str(facility_id) if facility_id else None,
            role=user_role,
        )
        return AnswerResponse(
            answer=(
                "This looks like a clinical question. For safety, the help "
                "assistant does not provide medical advice. Please consult "
                "the attending clinician, or open the Clinical Decision "
                "Support module for evidence-based guidance."
            ),
            suggested_links=[
                SuggestedLink(label="Clinical Decision Support", href="/cds"),
            ],
            confidence=0.95,
            model="guardrail",
        )

    # Hard guardrail: refuse if the query carries identifiers that suggest PHI
    if _PHI_RED_FLAGS.search(query):
        logger.warning(
            "help_bot_phi_blocked",
            facility_id=str(facility_id) if facility_id else None,
            role=user_role,
        )
        return AnswerResponse(
            answer=(
                "It looks like your question contains patient identifiers "
                "(MRN, phone, ID, email). Please remove personal information "
                "and ask the question generally. The help bot does not "
                "process patient data."
            ),
            suggested_links=[],
            confidence=1.0,
            model="guardrail",
        )

    screen = context or "unknown"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[role={user_role}][screen={screen}] {query.strip()}",
        },
    ]

    # Preferred provider: DeepSeek via the .env API key. This lets the bot
    # answer general questions (system help, greetings, jokes, education)
    # without a local AI service. Falls back to ai-service only when no
    # DeepSeek key is configured.
    if settings.deepseek_api_key:
        endpoint = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.6,
        }
        model_name = "deepseek-chat"
    else:
        endpoint = f"{_AI_SERVICE_URL.rstrip('/')}/v1/chat/completions"
        headers = {}
        payload = {
            "model": "qwen-72b",
            "messages": messages,
            "max_tokens": 512,
            "temperature": 0.2,
        }
        model_name = "qwen-72b"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            text = data["choices"][0]["message"]["content"].strip()
            return AnswerResponse(
                answer=text,
                suggested_links=suggested,
                confidence=0.7,
                model=model_name,
            )
        logger.warning(
            "help_bot_ai_error",
            status_code=response.status_code,
            body=response.text[:200],
        )
    except httpx.HTTPError as exc:
        logger.warning("help_bot_ai_unavailable", error=str(exc))

    # Fallback when the AI provider is unavailable
    return AnswerResponse(
        answer=(
            "I could not reach the AI service right now. Please try again "
            "in a moment, or ask your facility administrator. You can also "
            "press Cmd+K to open the command palette and search the system."
        ),
        suggested_links=suggested,
        confidence=0.3,
        model="fallback",
    )
