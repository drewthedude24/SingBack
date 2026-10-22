"""Regression coverage for MediaRecorder containers without duration metadata."""
import subprocess
import wave

import pytest

from backend.app.config import Settings
from backend.app.errors import ApiError
from backend.app.services.audio_service import AudioService
from backend.tests.test_rooms import action, create, join, ready_and_start, wait_for_results


def encode_recording(ffmpeg: str, source: bytes, kind: str) -> bytes:
    # Writing to a pipe makes WebM non-seekable, like MediaRecorder. Fragmented
    # MP4 is the browser/Safari-style alternative to a finalized M4A file.
    args = {
        "webm": ["-c:a", "libopus", "-f", "webm"],
        "mp4": ["-c:a", "aac", "-movflags", "frag_keyframe+empty_moov+default_base_moof", "-f", "mp4"],
        "ogg": ["-c:a", "libopus", "-f", "ogg"],
    }[kind]
    return subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
        "-vn", *args, "pipe:1"], input=source, capture_output=True, check=True, timeout=20).stdout


@pytest.mark.parametrize("kind", ["webm", "mp4", "ogg", "wav"])
def test_measure_and_mix_mobile_containers(tmp_path, vocal_wav, kind):
    settings = Settings(runtime_root=tmp_path)
    service = AudioService(settings)
    source = vocal_wav if kind == "wav" else encode_recording(service.ffmpeg_bin, vocal_wav, kind)
    raw = tmp_path / f"input.{kind}"
    raw.write_bytes(source)
    if kind == "webm":
        old_probe = subprocess.run([service.ffmpeg_bin, "-hide_banner", "-i", str(raw), "-f", "null", "-"],
            capture_output=True, timeout=20)
        assert b"Duration: N/A" in old_probe.stderr  # Reproduces the old rejection.
    artifact = service.process_recording(session_id="test-session", player_id="test-player",
        upload_bytes=source, mime_type=f"audio/{kind}",
        instrumental_path=settings.song_assets_root / "summer-day/instrumental.wav", preroll_ms=100)
    assert artifact.detected_duration_ms == pytest.approx(1200, abs=100)
    assert not artifact.silent
    assert (settings.session_media_root / "test-session/test-player/mix.mp3").stat().st_size > 1000
    with wave.open(str(artifact.vocal_path), "rb") as normalized:
        assert normalized.getnframes() / normalized.getframerate() == pytest.approx(10)


def test_rejects_invalid_or_overlong_decoded_audio(tmp_path):
    service = AudioService(Settings(runtime_root=tmp_path))
    invalid = tmp_path / "invalid.webm"
    invalid.write_bytes(b"not an audio recording")
    with pytest.raises(ApiError) as exc:
        service._probe_duration_ms(invalid)
    assert exc.value.code == "INVALID_AUDIO"
    overlong = tmp_path / "long.wav"
    with wave.open(str(overlong), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(31 * 16000 * 2))
    with pytest.raises(ApiError) as exc:
        service._probe_duration_ms(overlong)
    assert exc.value.code == "INVALID_RECORDING_DURATION"


def test_mobile_formats_complete_an_online_round(client, vocal_wav):
    host = create(client, "WebM phone")
    guest = join(client, host, "MP4 phone")
    ready_and_start(client, [host, guest])
    ffmpeg = client.app.state.audio_service.ffmpeg_bin
    for member, kind, mime in [(host, "webm", "audio/webm;codecs=opus"), (guest, "mp4", "audio/mp4")]:
        recording = encode_recording(ffmpeg, vocal_wav, kind)
        response = action(client, member, "recordings",
            data={"mimeType": mime, "prerollMs": "100", "durationMs": "1200"},
            files={"file": (f"phone.{kind}", recording, mime)})
        assert response.status_code == 200, response.text
    results = wait_for_results(client, host)["results"]
    assert len(results["performances"]) == 2
    for performance in results["performances"]:
        assert len(performance["evidence"]["playerWaveform"]) == 180
        assert client.get(performance["mixUrl"]).status_code == 200
