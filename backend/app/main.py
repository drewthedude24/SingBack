from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHttpException

from backend.app.api import health, sessions, songs
from backend.app.config import Settings
from backend.app.errors import ApiError, api_error_handler
from backend.app.integrations.elevenlabs import ElevenLabsService
from backend.app.integrations.gemini import GeminiFeedbackService
from backend.app.scoring.service import ScoringService
from backend.app.services.analysis_service import AnalysisService
from backend.app.services.audio_service import AudioService
from backend.app.services.session_service import SessionService
from backend.app.services.song_catalog import SongCatalog


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.session_media_root.mkdir(parents=True, exist_ok=True)
    settings.private_media_root.mkdir(parents=True, exist_ok=True)
    settings.narration_media_root.mkdir(parents=True, exist_ok=True)
    song_catalog = SongCatalog(settings.song_manifest_path, settings.repository_root)
    audio_service = AudioService(settings)
    elevenlabs_service = ElevenLabsService(settings)
    gemini_service = GeminiFeedbackService(settings)
    analysis_service = AnalysisService(
        scoring=ScoringService(),
        elevenlabs=elevenlabs_service,
        gemini=gemini_service,
        reference_path_resolver=song_catalog.asset_path,
    )
    session_service = SessionService(song_catalog, analysis_service)

    application = FastAPI(title="SingBack API", version="0.1.0")
    application.state.settings = settings
    application.state.song_catalog = song_catalog
    application.state.audio_service = audio_service
    application.state.elevenlabs_service = elevenlabs_service
    application.state.gemini_service = gemini_service
    application.state.analysis_service = analysis_service
    application.state.session_service = session_service

    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.add_exception_handler(ApiError, api_error_handler)

    @application.exception_handler(StarletteHttpException)
    async def http_error_handler(_, exc: StarletteHttpException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = (
            str(exc.detail) if exc.detail else "The request could not be completed."
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "retryable": False,
                    "details": {},
                }
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
        issues = [
            {key: value for key, value in issue.items() if key != "ctx"}
            for issue in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request did not match the API contract.",
                    "retryable": False,
                    "details": {"issues": issues},
                }
            },
        )

    application.include_router(health.router, prefix="/api")
    application.include_router(songs.router, prefix="/api")
    application.include_router(sessions.router, prefix="/api")
    application.mount(
        "/media/songs",
        StaticFiles(directory=settings.song_assets_root),
        name="song-media",
    )
    application.mount(
        "/media/sessions",
        StaticFiles(directory=settings.session_media_root),
        name="session-media",
    )
    application.mount(
        "/media/narration",
        StaticFiles(directory=settings.narration_media_root),
        name="narration-media",
    )
    return application


app = create_app()
