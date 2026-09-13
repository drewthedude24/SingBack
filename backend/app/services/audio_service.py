from __future__ import annotations

import math
import re
import shutil
import subprocess
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path

from backend.app.config import Settings
from backend.app.errors import ApiError

MIME_SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
}
_DURATION_PATTERN = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class AudioArtifact:
    detected_duration_ms: int
    applied_offset_ms: int
    silent: bool
    mix_url: str
    vocal_path: Path


def resolve_ffmpeg(explicit_binary: str | None) -> str:
    if explicit_binary:
        return explicit_binary
    system_binary = shutil.which("ffmpeg")
    if system_binary:
        return system_binary
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "FFmpeg is unavailable. Install backend requirements or set FFMPEG_BIN."
        ) from exc


class AudioService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self.ffmpeg_bin = resolve_ffmpeg(settings.ffmpeg_bin)

    def process_recording(
        self,
        *,
        session_id: str,
        player_id: str,
        upload_bytes: bytes,
        mime_type: str,
        instrumental_path: Path,
        preroll_ms: int,
    ) -> AudioArtifact:
        suffix = MIME_SUFFIXES.get(mime_type.split(";", 1)[0].strip().lower())
        if suffix is None:
            raise ApiError(
                415,
                "UNSUPPORTED_AUDIO_TYPE",
                "Upload WebM, Ogg, WAV, MP3, or M4A audio.",
            )
        if not upload_bytes:
            raise ApiError(400, "EMPTY_RECORDING", "The uploaded recording is empty.")

        private_player_dir = self._settings.private_media_root / session_id / player_id
        public_player_dir = self._settings.session_media_root / session_id / player_id
        private_player_dir.mkdir(parents=True, exist_ok=True)
        public_player_dir.mkdir(parents=True, exist_ok=True)
        raw_path = private_player_dir / f"raw{suffix}"
        vocal_path = private_player_dir / "vocal.wav"
        mix_path = public_player_dir / "mix.mp3"
        raw_path.write_bytes(upload_bytes)

        detected_duration_ms = self._probe_duration_ms(raw_path)
        applied_offset_ms = max(-2_000, min(preroll_ms, 5_000))
        self._normalize_vocal(raw_path, vocal_path, applied_offset_ms)
        silent = self._is_silent(vocal_path)
        self._mix(instrumental_path, vocal_path, mix_path)

        return AudioArtifact(
            detected_duration_ms=detected_duration_ms,
            applied_offset_ms=applied_offset_ms,
            silent=silent,
            mix_url=f"/media/sessions/{session_id}/{player_id}/mix.mp3",
            vocal_path=vocal_path,
        )

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            completed = subprocess.run(
                [self.ffmpeg_bin, *args],
                capture_output=True,
                text=True,
                timeout=self._settings.ffmpeg_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ApiError(
                503,
                "AUDIO_PROCESSING_UNAVAILABLE",
                "Audio processing is temporarily unavailable.",
                retryable=True,
            ) from exc
        if completed.returncode != 0:
            raise ApiError(
                422,
                "INVALID_AUDIO",
                "The uploaded file could not be decoded as audio.",
                details={"ffmpeg": completed.stderr[-500:]},
            )
        return completed

    def _probe_duration_ms(self, path: Path) -> int:
        try:
            completed = subprocess.run(
                [self.ffmpeg_bin, "-hide_banner", "-i", str(path), "-f", "null", "-"],
                capture_output=True,
                text=True,
                timeout=self._settings.ffmpeg_timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ApiError(
                503,
                "AUDIO_PROCESSING_UNAVAILABLE",
                "Audio processing is temporarily unavailable.",
                retryable=True,
            ) from exc
        match = _DURATION_PATTERN.search(completed.stderr)
        if match is None:
            raise ApiError(
                422, "INVALID_AUDIO", "The upload has no readable audio duration."
            )
        hours, minutes, seconds = match.groups()
        return round((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)

    def _normalize_vocal(
        self, raw_path: Path, vocal_path: Path, offset_ms: int
    ) -> None:
        if offset_ms >= 0:
            timing_filter = f"atrim=start={offset_ms / 1000:.3f},asetpts=PTS-STARTPTS"
        else:
            timing_filter = f"adelay={abs(offset_ms)}:all=1"
        # Singing recorded beside speaker playback is usually much quieter than
        # the prepared instrumental. Clean and compress the isolated mic before
        # mixing so soft takes remain audible without clipping loud takes.
        audio_filter = (
            f"{timing_filter},highpass=f=80,lowpass=f=10000,"
            "acompressor=threshold=-24dB:ratio=3:attack=5:release=80:makeup=8dB,"
            "volume=2.0,alimiter=limit=0.92,apad=whole_dur=10,atrim=duration=10"
        )
        self._run(
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(raw_path),
                "-af",
                audio_filter,
                "-ar",
                "44100",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(vocal_path),
            ]
        )

    def _mix(self, instrumental_path: Path, vocal_path: Path, mix_path: Path) -> None:
        self._run(
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(instrumental_path),
                "-i",
                str(vocal_path),
                "-filter_complex",
                (
                    "[0:a]volume=0.38[bed];[1:a]volume=1.35[voice];"
                    "[bed][voice]amix=inputs=2:duration=first:dropout_transition=0:"
                    "normalize=0,"
                    "alimiter=limit=0.95[out]"
                ),
                "-map",
                "[out]",
                "-t",
                "10",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-c:a",
                "libmp3lame",
                "-q:a",
                "3",
                str(mix_path),
            ]
        )

    @staticmethod
    def _is_silent(vocal_path: Path) -> bool:
        with wave.open(str(vocal_path), "rb") as wav_file:
            samples = array("h", wav_file.readframes(wav_file.getnframes()))
        if not samples:
            return True
        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
        return rms < 120
