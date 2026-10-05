"""Deterministic spoken text for queue announcements.

The spoken form is built here, away from the TTS vendor, so it can be unit
tested without a network call and so every provider says the same thing:
"OPD-023" becomes "O P D zero two three" and "Room 2" becomes "Room two".

Digits are the whole point. A ticket number read as a number ("OPD twenty
three") is ambiguous the moment two tickets differ only in their leading
zeros, so a code is always spelled one character at a time.
"""

from __future__ import annotations

import hashlib
import re

DIGIT_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

TEEN_WORDS = {
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
}

TENS_WORDS = {
    20: "twenty",
    30: "thirty",
    40: "forty",
    50: "fifty",
    60: "sixty",
    70: "seventy",
    80: "eighty",
    90: "ninety",
}

#: Longer keys first, so "a&e" is expanded before the bare "&".
ABBREVIATIONS = (
    ("a&e", "A and E"),
    ("opd", "O P D"),
    ("ipd", "I P D"),
    ("no.", "number "),
    ("dr.", "doctor "),
    ("&", " and "),
)

_NUMBER = re.compile(r"^[0-9]+$")
_TOKEN = re.compile(r"[A-Za-z0-9]+")


def _spell(token: str) -> str:
    """Spell a code one character at a time: OPD023 -> O P D zero two three."""

    parts = []
    for char in token:
        if char.isalpha():
            parts.append(char.upper())
        elif char.isdigit():
            parts.append(DIGIT_WORDS[char])
    return " ".join(parts)


def _say_number(token: str) -> str:
    """Say a plain number the way a person would: 2 -> two, 12 -> twelve.

    A leading zero, or more than two digits, means the token is an
    identifier rather than a quantity, so it is spelled instead.
    """

    if token.startswith("0") or len(token) > 2:
        return _spell(token)
    value = int(token)
    if value < 10:
        return DIGIT_WORDS[token]
    if value < 20:
        return TEEN_WORDS[value]
    tens = (value // 10) * 10
    ones = value % 10
    if ones == 0:
        return TENS_WORDS[tens]
    return f"{TENS_WORDS[tens]} {DIGIT_WORDS[str(ones)]}"


def _expand_abbreviations(text: str) -> str:
    """Replace the handful of spoken contractions the queue actually uses."""

    for source, spoken in ABBREVIATIONS:
        text = re.sub(re.escape(source), spoken, text, flags=re.IGNORECASE)
    return text


def normalise_for_speech(text: str, language: str = "en") -> str:
    """Turn ticket and room codes into something a speaker can read aloud.

    Only English is expanded today; other languages pass through unchanged
    rather than being mangled by English number words.
    """

    if language.lower() not in ("en", "en-us", "en-gb"):
        return " ".join(text.split())

    expanded = _expand_abbreviations(text)
    out: list[str] = []
    for raw in re.split(r"([\s,;:]+)", expanded):
        if not raw or not raw.strip():
            continue
        token = raw.strip(".,;:")
        if not token:
            continue
        if _NUMBER.match(token):
            out.append(_say_number(token))
        elif any(ch.isdigit() for ch in token):
            out.append(_spell(token))
        elif token.isupper() and len(token) <= 4 and token.isalpha():
            out.append(" ".join(token))
        else:
            out.append(token)
    spoken = re.sub(r"\s+", " ", " ".join(out)).strip()
    return spoken[0].upper() + spoken[1:] if spoken else spoken


def build_call_text(
    ticket_number: str, destination: str | None, recalled: bool = False
) -> str:
    """The words spoken when a ticket is called.

    @param ticket_number: The ticket's short number, e.g. OPD-023
    @param destination: Where the patient should go, e.g. Consultation Room 2
    @param recalled: True when this is a repeat call
    @returns A single sentence for the speaker
    """

    where = destination.strip() if destination else "the service desk"
    if recalled:
        return f"Ticket {ticket_number}, please proceed to {where}. This is a repeat call."
    return f"Ticket {ticket_number}, please proceed to {where}."


def cache_key(text: str, voice: str, model: str, audio_format: str) -> str:
    """Stable hash of everything that changes the produced audio."""

    payload = f"{text}|{voice}|{model}|{audio_format}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
