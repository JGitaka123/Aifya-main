"""AI help assistant: the in-app guide behind the User Guide tab.

Locks in the behaviour the User Guide panel depends on: a how-to
question points at the right module, clinical questions are refused,
patient identifiers are refused, the reported screen cannot smuggle a
prompt, and the assistant still answers gracefully when no model is
reachable.
"""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.services import help_bot
from app.services.help_bot import answer_help_query


def _go_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point both providers at nothing so no test touches the network."""
    monkeypatch.setattr(settings, "deepseek_api_key", "")
    monkeypatch.setattr(help_bot, "_AI_SERVICE_URL", "http://127.0.0.1:9")


async def test_a_how_to_question_suggests_the_matching_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registering a patient must point at the registration screen."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "How do I register a new patient?", context="/user-guide"
    )

    hrefs = [link.href for link in answer.suggested_links]
    assert "/patients/register" in hrefs
    assert answer.model != "guardrail"


async def test_a_clinical_question_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doses and diagnoses are redirected, never answered by the model."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "What dose of paracetamol should I give a child?"
    )

    assert answer.model == "guardrail"
    assert "clinical" in answer.answer.lower()
    assert [link.href for link in answer.suggested_links] == ["/clinical"]


async def test_patient_identifiers_are_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PHI never reaches the model; the user is asked to generalise."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "John Doe MRN 12345 phone 0712345678 needs a bed"
    )

    assert answer.model == "guardrail"
    assert "personal information" in answer.answer.lower()
    assert answer.suggested_links == []


async def test_the_assistant_still_guides_without_a_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No provider reachable: answer gracefully and keep the links."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "Where do I find pharmacy stock?", context="/user-guide"
    )

    assert answer.model == "fallback"
    assert answer.answer
    assert "/pharmacy" in [link.href for link in answer.suggested_links]


async def test_the_endpoint_answers_through_the_api(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The User Guide panel posts here; it must answer over HTTP."""
    _go_offline(monkeypatch)

    response = await client.post(
        "/api/v1/help/ask",
        json={"query": "How do I record a payment?", "context": "/user-guide"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert [link["href"] for link in body["suggested_links"]][0] == "/billing/pos"


async def test_the_endpoint_refuses_a_clinical_question(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The safety guardrail also holds at the HTTP boundary."""
    _go_offline(monkeypatch)

    response = await client.post(
        "/api/v1/help/ask",
        json={"query": "Which antibiotic treats pneumonia?"},
    )

    assert response.status_code == 200
    assert response.json()["model"] == "guardrail"


async def test_a_malformed_screen_hint_is_dropped(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bogus screen path is discarded, not forwarded to the model."""
    _go_offline(monkeypatch)

    response = await client.post(
        "/api/v1/help/ask",
        json={"query": "where is the lab", "context": "../../etc/passwd"},
    )

    assert response.status_code == 200
    assert response.json()["answer"]


async def test_an_empty_question_is_rejected(
    client: AsyncClient,
) -> None:
    """An empty prompt is a client error, not a model call."""
    response = await client.post(
        "/api/v1/help/ask", json={"query": ""}
    )

    assert response.status_code == 422


async def test_payroll_points_at_the_hr_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Payroll lives under HR; the assistant must not link to a dead page."""
    _go_offline(monkeypatch)

    answer = await answer_help_query("How do I run payroll?", context="/user-guide")

    hrefs = [link.href for link in answer.suggested_links]
    assert "/hr/payroll" in hrefs
    assert "/finance/payroll" not in hrefs


async def test_a_payment_question_points_at_the_cashier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Counter payments belong to the Point of Sale screen."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "Where does the cashier take payment from a patient?", context="/billing"
    )

    assert [link.href for link in answer.suggested_links][0] == "/billing/pos"


async def test_the_consultation_room_is_its_own_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The doctor's queue is the Consultation Room, not the OPD screen."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "How do I call the next patient into the consultation room?",
        context="/user-guide",
    )

    assert [link.href for link in answer.suggested_links][0] == "/consultation"


async def test_the_opd_queue_is_reachable_from_the_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The nurse's queue lives on the OPD screen."""
    _go_offline(monkeypatch)

    answer = await answer_help_query(
        "How do I call the next ticket in the opd queue?", context="/user-guide"
    )

    assert "/opd" in [link.href for link in answer.suggested_links]


_WEB_SCREENS_DIR = (
    Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "app" / "[locale]"
)


def _shipped_screens() -> set[str]:
    """Every screen the web app actually ships, as an in-app path."""
    if not _WEB_SCREENS_DIR.is_dir():
        pytest.skip("web app source is not available in this checkout")

    screens: set[str] = set()
    for page in _WEB_SCREENS_DIR.rglob("page.tsx"):
        segments = [
            part
            for part in page.parent.relative_to(_WEB_SCREENS_DIR).parts
            if not (part.startswith("[") and part.endswith("]"))
        ]
        screens.add("/" + "/".join(segments) if segments else "/")
    return screens


def test_every_suggested_link_is_a_real_screen() -> None:
    """A dead link is worse than no link; the catalogue must only hold real screens."""
    screens = _shipped_screens()

    missing = [
        href
        for href, _label, _keywords in help_bot._MODULE_KEYWORDS
        if href not in screens
    ]
    assert missing == []
    assert "/clinical" in screens  # the clinical guardrail destination
