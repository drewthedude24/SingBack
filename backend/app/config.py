from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    repository_root: Path = REPOSITORY_ROOT
    runtime_root: Path = REPOSITORY_ROOT / "runtime"
    max_upload_bytes: int = 20 * 1024 * 1024
    ffmpeg_timeout_seconds: int = 45
    ffmpeg_bin: str | None = field(default_factory=lambda: os.getenv("FFMPEG_BIN"))
    gemini_api_key: str | None = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY") or None
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    )
    elevenlabs_api_key: str | None = field(
        default_factory=lambda: os.getenv("ELEVENLABS_API_KEY") or None
    )
    elevenlabs_voice_id: str = field(
        default_factory=lambda: os.getenv(
            "ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"
        )
    )
    elevenlabs_tts_model: str = field(
        default_factory=lambda: os.getenv(
            "ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5"
        )
    )
    elevenlabs_scribe_model: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_SCRIBE_MODEL", "scribe_v2")
    )
    external_api_timeout_seconds: float = 12.0
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )

    @property
    def song_manifest_path(self) -> Path:
        return self.repository_root / "assets" / "songs" / "manifest.json"

    @property
    def song_assets_root(self) -> Path:
        return self.repository_root / "assets" / "songs"

    @property
    def session_media_root(self) -> Path:
        return self.runtime_root / "sessions"

    @property
    def private_media_root(self) -> Path:
        return self.runtime_root / "private"

    @property
    def narration_media_root(self) -> Path:
        return self.runtime_root / "narration"
