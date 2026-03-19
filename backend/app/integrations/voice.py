"""
Voice Input — Transcription for Telegram Voice Messages

Receives OGG audio from Telegram voice messages, transcribes using
OpenAI Whisper API (or local whisper if available), and returns text.
"""

import io
import logging
import tempfile
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"


async def transcribe_voice(audio_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Transcribe audio bytes to text.

    Tries OpenAI Whisper API first, then falls back to local whisper
    if the openai_api_key is not configured.

    Args:
        audio_bytes: Raw audio data (typically OGG format from Telegram).
        filename: Original filename (used for format hint).

    Returns:
        Transcribed text string.

    Raises:
        RuntimeError: If transcription fails.
    """
    if settings.openai_api_key:
        return await _transcribe_openai(audio_bytes, filename)
    else:
        return await _transcribe_local(audio_bytes, filename)


async def _transcribe_openai(audio_bytes: bytes, filename: str) -> str:
    """Transcribe using the OpenAI Whisper API."""
    logger.debug("Transcribing voice message via OpenAI Whisper API")

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            WHISPER_API_URL,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            files={"file": (filename, io.BytesIO(audio_bytes), "audio/ogg")},
            data={"model": "whisper-1"},
        )

    if response.status_code != 200:
        detail = response.text[:200]
        logger.error(f"Whisper API error {response.status_code}: {detail}")
        raise RuntimeError(f"Whisper API error: {response.status_code}")

    result = response.json()
    text = result.get("text", "").strip()
    logger.info(f"Transcribed voice message: {text[:80]}...")
    return text


async def _transcribe_local(audio_bytes: bytes, filename: str) -> str:
    """Transcribe using local whisper (python package).

    Requires the `openai-whisper` package to be installed:
        pip install openai-whisper
    """
    try:
        import whisper  # type: ignore[import-untyped]
    except ImportError:
        raise RuntimeError(
            "Voice transcription requires either OPENAI_API_KEY for the Whisper API "
            "or the 'openai-whisper' package installed locally. "
            "Set OPENAI_API_KEY in your .env or run: pip install openai-whisper"
        )

    logger.debug("Transcribing voice message via local whisper model")

    # Write audio to a temp file (whisper needs a file path)
    suffix = Path(filename).suffix or ".ogg"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        import asyncio
        loop = asyncio.get_event_loop()
        # Run whisper in a thread to avoid blocking the event loop
        text = await loop.run_in_executor(None, _run_local_whisper, tmp_path)
        logger.info(f"Transcribed voice message (local): {text[:80]}...")
        return text
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _run_local_whisper(file_path: str) -> str:
    """Run local whisper model synchronously (called in executor)."""
    import whisper  # type: ignore[import-untyped]
    model = whisper.load_model("base")
    result = model.transcribe(file_path)
    return result.get("text", "").strip()
