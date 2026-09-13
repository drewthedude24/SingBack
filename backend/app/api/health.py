from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "ffmpeg": bool(request.app.state.audio_service.ffmpeg_bin),
        "gemini": "unconfigured",
        "elevenlabs": "unconfigured",
    }
