from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

from backend.app.errors import ApiError
from backend.app.models import NarrationCue, NarrationResponse
from backend.app.room_models import ReadyRequest, RoomCredentials, RoomNameRequest, RoomView

router = APIRouter(prefix="/rooms", tags=["online rooms"])
bearer = HTTPBearer(auto_error=False)


def member_token(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "ROOM_TOKEN_REQUIRED", "Join the room on this device first.")
    return credentials.credentials


Token = Annotated[str, Depends(member_token)]


@router.post("", response_model=RoomCredentials, status_code=201)
def create_room(payload: RoomNameRequest, request: Request):
    return request.app.state.room_service.create(payload.display_name)


@router.post("/{code}/join", response_model=RoomCredentials, status_code=201)
def join_room(code: str, payload: RoomNameRequest, request: Request):
    return request.app.state.room_service.join(code, payload.display_name)


@router.get("/{code}", response_model=RoomView)
def get_room(code: str, request: Request, token: Token):
    return request.app.state.room_service.view(code, token)


@router.post("/{code}/ready", response_model=RoomView)
def ready(code: str, payload: ReadyRequest, request: Request, token: Token):
    return request.app.state.room_service.ready(code, token, payload.ready)


@router.post("/{code}/start", response_model=RoomView)
def start(code: str, request: Request, token: Token):
    return request.app.state.room_service.start(code, token)


@router.post("/{code}/listened", response_model=RoomView)
def listened(code: str, request: Request, token: Token):
    return request.app.state.room_service.listened(code, token)


@router.post("/{code}/retry", response_model=RoomView)
def retry(code: str, request: Request, token: Token):
    return request.app.state.room_service.retry(code, token)


@router.post("/{code}/rematch", response_model=RoomView)
def rematch(code: str, request: Request, token: Token):
    return request.app.state.room_service.rematch(code, token)


@router.post("/{code}/skip", response_model=RoomView)
def skip(code: str, request: Request, token: Token):
    return request.app.state.room_service.skip(code, token)


@router.delete("/{code}/players/{player_id}", response_model=RoomView)
def remove(code: str, player_id: str, request: Request, token: Token):
    return request.app.state.room_service.remove(code, token, player_id)


@router.post("/{code}/leave", status_code=204)
def leave(code: str, request: Request, token: Token):
    request.app.state.room_service.leave(code, token)


@router.get("/{code}/narration/{cue}", response_model=NarrationResponse)
def narration(code: str, cue: NarrationCue, request: Request, token: Token):
    text = request.app.state.room_service.narration_text(code, token, cue)
    result = request.app.state.elevenlabs_service.narrate(text)
    return NarrationResponse(cue=cue, text=text, audioUrl=result.audio_url, source=result.source)


@router.get("/{code}/mixes/{player_id}/mix.mp3")
def mix(code: str, player_id: str, request: Request):
    path = request.app.state.room_service.mix_path(code, player_id)
    return FileResponse(path, media_type="audio/mpeg")


@router.post("/{code}/recordings", response_model=RoomView)
async def upload(code: str, request: Request, token: Token,
                 file: Annotated[UploadFile, File()],
                 mime_type: Annotated[str, Form(alias="mimeType")],
                 preroll_ms: Annotated[int, Form(alias="prerollMs")],
                 duration_ms: Annotated[int, Form(alias="durationMs")]):
    if not 0 < duration_ms <= 30_000:
        raise ApiError(400, "INVALID_RECORDING_DURATION", "Recording duration is out of range.")
    if file.content_type and file.content_type.split(";", 1)[0] != mime_type.split(";", 1)[0]:
        raise ApiError(400, "MIME_TYPE_MISMATCH", "Upload and form MIME types do not match.")
    service = request.app.state.room_service
    session_id, player_id, instrumental = service.reserve_upload(code, token)
    try:
        data = await file.read(request.app.state.settings.max_upload_bytes + 1)
        if len(data) > request.app.state.settings.max_upload_bytes:
            raise ApiError(413, "RECORDING_TOO_LARGE", "The recording exceeds the 20 MB limit.")
        artifact = await run_in_threadpool(request.app.state.audio_service.process_recording,
            session_id=session_id, player_id=player_id, upload_bytes=data, mime_type=mime_type,
            instrumental_path=instrumental, preroll_ms=preroll_ms)
        return service.finish_upload(code, token, artifact)
    except BaseException:
        service.cancel_upload(code, token)
        raise
