"""Dictation (audio transcription) endpoints."""

import math

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.deps import CurrentUser, DbSession
from app.services.transcription import transcription_service
from app.services.usage import usage_service

router = APIRouter()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float
    remaining_seconds: int


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile,
    language: str = "fr",
) -> TranscriptionResponse:
    """Transcribe an audio file to text.

    Accepts WebM, WAV, MP3, etc. Max 10 MB.
    """
    tenant_id = user.tenant_id

    # Check quota before processing
    allowed, error = await usage_service.check_transcription_quota(db, tenant_id)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error,
        )

    # Read audio content
    audio_data = await file.read()
    if not audio_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )

    if len(audio_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file too large (max 10 MB)",
        )

    # Transcribe via Mistral Voxtral
    text, duration = await transcription_service.transcribe(
        audio_data=audio_data,
        filename=file.filename or "audio.webm",
        language=language,
    )

    # Record usage
    seconds_used = math.ceil(duration)
    await usage_service.record_transcription(db, tenant_id, seconds_used)
    await db.commit()

    # Compute remaining quota
    usage = await usage_service.get_or_create_usage(db, tenant_id)
    from sqlalchemy import select
    from app.models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()
    remaining = max(0, tenant.max_transcription_seconds - usage.transcription_seconds)

    return TranscriptionResponse(
        text=text,
        duration_seconds=duration,
        remaining_seconds=remaining,
    )
