"""
AI Help Bot router — lightweight in-app navigation/help assistant.

Security:
- Clinical questions are refused via _CLINICAL_RED_FLAGS in services/help_bot.py.
- PHI identifiers (MRN, phone, ID, email) cause an immediate refusal.
- TODO(production): rate-limit per user (e.g. 30 req/min/user) using Redis. The
  centrally configured slowapi/RateLimitMiddleware should cover this endpoint.
- Query text is NEVER logged; only metadata (role, facility_id) is logged.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.services.help_bot import AnswerResponse, answer_help_query

router = APIRouter()


# Only a plain in-app path is accepted, so the screen hint cannot be used
# to smuggle arbitrary text into the model prompt.
_SCREEN_PATH_RE = re.compile(r"^/[A-Za-z0-9/_-]{0,120}$")


class HelpAskRequest(BaseModel):
    """
    Request to ask the help bot.

    @param query: User question (1-1000 chars)
    @param context: Screen the user is on, e.g. /user-guide
    """

    query: str = Field(..., min_length=1, max_length=1000)
    context: str | None = Field(None, max_length=200)

    def screen(self) -> str | None:
        """
        Validate the reported screen path.

        @returns The normalised path, or None when absent or malformed
        """
        if not self.context:
            return None
        candidate = self.context.strip()
        if not _SCREEN_PATH_RE.match(candidate):
            return None
        return candidate


@router.post("/ask", response_model=AnswerResponse)
async def ask_help_bot(
    data: HelpAskRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> AnswerResponse:
    """
    Ask the help bot a navigation / how-do-I question.
    Clinical questions are refused — the user is redirected to a clinician
    or to the Clinical Decision Support module.

    @param data: Help question, plus the screen it was asked from
    @param current_user: Authenticated user from JWT (used for role + tenant)
    @returns Help bot answer with suggested links
    """
    role = current_user.roles[0] if current_user.roles else "staff"
    return await answer_help_query(
        query=data.query,
        user_role=role,
        facility_id=current_user.facility_id,
        context=data.screen(),
    )
