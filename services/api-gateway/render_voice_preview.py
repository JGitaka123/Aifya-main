"""Render and play a queue announcement with the exact voice the system uses.

Run from services/api-gateway so the project .env (TTS_PROVIDER=edge,
TTS_VOICE=en-KE-AsiliaNeural) is loaded. Needs internet, because the Edge
neural voices come from Microsoft's Read Aloud endpoint.
"""

import asyncio
import os

from app.config import settings
from app.services.voice.text import build_call_text, normalise_for_speech
from app.services.voice.tts_provider import provider_from_settings

TICKET = os.environ.get("PREVIEW_TICKET", "OPD-001")
DESTINATION = os.environ.get("PREVIEW_DEST", "Consultation Room 3")


def main() -> None:
    text = build_call_text(TICKET, DESTINATION)
    spoken = normalise_for_speech(text, settings.tts_language)
    provider = provider_from_settings()

    print("provider :", settings.tts_provider)
    print("voice    :", settings.tts_voice)
    print("script   :", text)
    print("spoken   :", spoken)
    print("engine   :", type(provider).__name__ if provider else None)
    if provider is None:
        raise SystemExit("Voice is disabled by current settings.")

    async def render():
        return await provider.synthesise(
            spoken,
            voice=settings.tts_voice,
            model=settings.tts_model,
            audio_format="mp3",
            language=settings.tts_language,
        )

    audio = asyncio.run(render())
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voice_preview.mp3")
    with open(out, "wb") as handle:
        handle.write(audio.data)
    print("rendered :", out, len(audio.data), "bytes, voice:", audio.voice)

    if os.name == "nt":
        os.startfile(out)  # noqa: S606 - open the clip in the default player


if __name__ == "__main__":
    main()
