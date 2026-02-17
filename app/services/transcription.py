"""Transcription service using Mistral Voxtral API."""

import io
import logging

import httpx

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MISTRAL_TRANSCRIPTION_URL = "https://api.mistral.ai/v1/audio/transcriptions"


class TranscriptionService:
    """Audio-to-text transcription via Mistral Voxtral."""

    def __init__(self) -> None:
        self.api_key = settings.mistral_api_key
        self.model = settings.transcription_model

    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.webm",
        language: str = "fr",
    ) -> tuple[str, float]:
        """Transcribe audio data using Mistral Voxtral.

        Returns:
            Tuple of (transcribed_text, duration_seconds).
        """
        audio_file = io.BytesIO(audio_data)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                MISTRAL_TRANSCRIPTION_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                },
                files={
                    "file": (filename, audio_file, "audio/webm"),
                },
                data={
                    "model": self.model,
                    "language": language,
                },
            )
            response.raise_for_status()

        result = response.json()
        text: str = result.get("text", "")
        # Duration comes from usage.prompt_audio_seconds in Mistral's response
        usage = result.get("usage", {})
        duration: float = float(usage.get("prompt_audio_seconds", 0))

        logger.info(
            "Transcribed %.1fs of audio (%d bytes) → %d chars [model=%s]",
            duration,
            len(audio_data),
            len(text),
            self.model,
        )

        return text, duration


transcription_service = TranscriptionService()
