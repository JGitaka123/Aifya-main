"""Shared helper for deciding whether a messaging provider is usable.

A value copied from ``.env.example`` (``your_africastalking_username`` and
friends) is present but not real. Treating it as configured makes the API call
the provider with bogus credentials, which surfaces as an opaque rejection
instead of a clear "not configured" message.
"""

from __future__ import annotations

import re
from typing import Final

_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(
    r"^(your_|change_me|replace_with|xxx|placeholder|dummy|todo)",
    re.IGNORECASE,
)


def is_set(value: str | None) -> bool:
    """
    Whether a configured value is real rather than a shipped placeholder.

    @param value: Raw setting value
    @returns True when the value is present and not a placeholder
    """
    if not value or not value.strip():
        return False
    return _PLACEHOLDER_RE.match(value.strip()) is None