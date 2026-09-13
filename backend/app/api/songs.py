from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.models import SongPublic

router = APIRouter(tags=["songs"])


@router.get("/songs", response_model=list[SongPublic], response_model_by_alias=True)
def list_songs(request: Request) -> list[SongPublic]:
    return request.app.state.song_catalog.all_public()
