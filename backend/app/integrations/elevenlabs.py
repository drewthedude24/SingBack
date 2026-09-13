from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx

from backend.app.config import Settings


@dataclass(frozen=True)
class TranscriptResult:
    text: str | None
    words: list[dict[str, float | str]]
    source: str


@dataclass(frozen=True)
class NarrationResult:
    audio_url: str | None
    source: str


class ElevenLabsService:
    """Scribe and TTS adapter that never blocks the core game on API failure."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        settings.narration_media_root.mkdir(parents=True, exist_ok=True)

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._voice_id)

    def transcribe(self, audio_path: Path) -> TranscriptResult:
        if not self._api_key:
            return TranscriptResult(text=None, words=[], source="unavailable")
        try:
            with audio_path.open("rb") as audio_file, httpx.Client(
                timeout=self._settings.external_api_timeout_seconds
            ) as client:
                response = client.post(
                    "https://api.elevenlabs.io/v1/speech-to-text",
                    headers={"xi-api-key": self._api_key},
                    files={"file": (audio_path.name, audio_file, "audio/wav")},
                    data={
                        "model_id": self._settings.elevenlabs_scribe_model,
                        "language_code": "eng",
                        "diarize": "false",
                    },
                )
                response.raise_for_status()
            payload = response.json()
            words = [
                {
                    "text": str(word.get("text", "")),
                    "start": float(word.get("start", 0.0)),
                    "end": float(word.get("end", 0.0)),
                }
                for word in payload.get("words", [])
                if word.get("type") == "word"
            ]
            text = str(payload.get("text", "")).strip() or None
            return TranscriptResult(text=text, words=words, source="elevenlabs")
        except (OSError, ValueError, TypeError, httpx.HTTPError):
            return TranscriptResult(text=None, words=[], source="unavailable")

    def narrate(self, text: str) -> NarrationResult:
        if not self._api_key:
            return NarrationResult(audio_url=None, source="fallback")
        cache_key = hashlib.sha256(
            f"{self._voice_id}\0{self._settings.elevenlabs_tts_model}\0{text}".encode()
        ).hexdigest()[:24]
        destination = self._settings.narration_media_root / f"{cache_key}.mp3"
        audio_url = f"/media/narration/{destination.name}"
        if destination.is_file() and destination.stat().st_size > 1_000:
            return NarrationResult(audio_url=audio_url, source="elevenlabs")
        try:
            with httpx.Client(
                timeout=self._settings.external_api_timeout_seconds
            ) as client:
                response = client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}",
                    params={"output_format": "mp3_44100_128"},
                    headers={
                        "xi-api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": text,
                        "model_id": self._settings.elevenlabs_tts_model,
                        "voice_settings": {
                            "stability": 0.48,
                            "similarity_boost": 0.72,
                            "style": 0.35,
                            "use_speaker_boost": True,
                        },
                    },
                )
                response.raise_for_status()
            if len(response.content) <= 1_000:
                return NarrationResult(audio_url=None, source="fallback")
            destination.write_bytes(response.content)
            return NarrationResult(audio_url=audio_url, source="elevenlabs")
        except (OSError, httpx.HTTPError):
            return NarrationResult(audio_url=None, source="fallback")
