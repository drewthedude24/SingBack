from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict[str, str | bool]:
    return {
        "status": "ok",
        "ffmpeg": bool(request.app.state.audio_service.ffmpeg_bin),
        "gemini": (
            "configured"
            if request.app.state.gemini_service.configured
            else "unconfigured"
        ),
        "elevenlabs": (
            "configured"
            if request.app.state.elevenlabs_service.configured
            else "unconfigured"
        ),
    }
