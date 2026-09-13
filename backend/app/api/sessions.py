from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile

from backend.app.errors import ApiError
from backend.app.models import (
    CreateSessionRequest,
    FinalResults,
    NarrationCue,
    NarrationResponse,
    RecordingResponse,
    RevealCompleteRequest,
    RevealResults,
    SessionView,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post(
    "", response_model=SessionView, response_model_by_alias=True, status_code=201
)
def create_session(payload: CreateSessionRequest, request: Request) -> SessionView:
    return request.app.state.session_service.create(
        payload.player_names, payload.song_id
    )


@router.get("/{session_id}", response_model=SessionView, response_model_by_alias=True)
def get_session(session_id: str, request: Request) -> SessionView:
    state = request.app.state.session_service.get(session_id)
    return request.app.state.session_service.view(state)


@router.get(
    "/{session_id}/narration/{cue}",
    response_model=NarrationResponse,
    response_model_by_alias=True,
)
def narration(
    session_id: str, cue: NarrationCue, request: Request
) -> NarrationResponse:
    text = request.app.state.session_service.narration_text(session_id, cue)
    result = request.app.state.elevenlabs_service.narrate(text)
    return NarrationResponse(
        cue=cue,
        text=text,
        audioUrl=result.audio_url,
        source=result.source,
    )


@router.post(
    "/{session_id}/start", response_model=SessionView, response_model_by_alias=True
)
def start_session(session_id: str, request: Request) -> SessionView:
    from backend.app.models import Phase

    return request.app.state.session_service.transition(
        session_id, Phase.LOBBY, Phase.LISTEN
    )


@router.post(
    "/{session_id}/reference-complete",
    response_model=SessionView,
    response_model_by_alias=True,
)
def reference_complete(session_id: str, request: Request) -> SessionView:
    from backend.app.models import Phase

    return request.app.state.session_service.transition(
        session_id, Phase.LISTEN, Phase.TURN_INTRO
    )


@router.post(
    "/{session_id}/next-player",
    response_model=SessionView,
    response_model_by_alias=True,
)
def next_player(session_id: str, request: Request) -> SessionView:
    return request.app.state.session_service.advance_player(session_id)


@router.post(
    "/{session_id}/recordings",
    response_model=RecordingResponse,
    response_model_by_alias=True,
)
async def upload_recording(
    session_id: str,
    request: Request,
    file: Annotated[UploadFile, File()],
    player_id: Annotated[str, Form(alias="playerId")],
    mime_type: Annotated[str, Form(alias="mimeType")],
    recording_start_perf_ms: Annotated[float, Form(alias="recordingStartPerfMs")],
    clock_sample_perf_ms: Annotated[float, Form(alias="clockSamplePerfMs")],
    clock_sample_audio_sec: Annotated[float, Form(alias="clockSampleAudioSec")],
    planned_playback_audio_sec: Annotated[float, Form(alias="plannedPlaybackAudioSec")],
    preroll_ms: Annotated[int, Form(alias="prerollMs")],
    duration_ms: Annotated[int, Form(alias="durationMs")],
    is_demo_fixture: Annotated[bool, Form(alias="isDemoFixture")] = False,
) -> RecordingResponse:
    del recording_start_perf_ms, clock_sample_perf_ms, clock_sample_audio_sec
    del planned_playback_audio_sec, is_demo_fixture
    if duration_ms <= 0 or duration_ms > 30_000:
        raise ApiError(
            400, "INVALID_RECORDING_DURATION", "Recording duration is out of range."
        )

    session_service = request.app.state.session_service
    state = session_service.active_player(session_id, player_id)
    upload_bytes = await file.read(request.app.state.settings.max_upload_bytes + 1)
    if len(upload_bytes) > request.app.state.settings.max_upload_bytes:
        raise ApiError(
            413, "RECORDING_TOO_LARGE", "The recording exceeds the 20 MB limit."
        )
    if (
        file.content_type
        and file.content_type.split(";", 1)[0] != mime_type.split(";", 1)[0]
    ):
        raise ApiError(
            400, "MIME_TYPE_MISMATCH", "Upload and form MIME types do not match."
        )

    instrumental_path = request.app.state.song_catalog.asset_path(
        state.song.instrumental_path
    )
    artifact = request.app.state.audio_service.process_recording(
        session_id=session_id,
        player_id=player_id,
        upload_bytes=upload_bytes,
        mime_type=mime_type,
        instrumental_path=instrumental_path,
        preroll_ms=preroll_ms,
    )
    return session_service.add_recording(session_id, player_id, artifact)


@router.post(
    "/{session_id}/finalize", response_model=RevealResults, response_model_by_alias=True
)
def finalize_session(session_id: str, request: Request) -> RevealResults:
    return request.app.state.session_service.finalize(session_id)


@router.get(
    "/{session_id}/results", response_model=RevealResults, response_model_by_alias=True
)
def reveal_results(session_id: str, request: Request) -> RevealResults:
    state = request.app.state.session_service.get(session_id)
    return request.app.state.session_service.reveal_results(state)


@router.post(
    "/{session_id}/reveal-complete",
    response_model=SessionView,
    response_model_by_alias=True,
)
def reveal_complete(
    session_id: str, payload: RevealCompleteRequest, request: Request
) -> SessionView:
    return request.app.state.session_service.complete_reveal(
        session_id, payload.reveal_ids
    )


@router.get(
    "/{session_id}/results/final",
    response_model=FinalResults,
    response_model_by_alias=True,
)
def final_results(session_id: str, request: Request) -> FinalResults:
    return request.app.state.session_service.final_results(session_id)
