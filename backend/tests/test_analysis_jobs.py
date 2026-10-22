import time
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.scoring.service import ScoringService
from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.integrations.elevenlabs import TranscriptResult
from backend.app.models import PerformanceEvidence, Score
from backend.app.services.analysis_service import AnalysisService
from backend.app.services.audio_service import AudioArtifact
from backend.app.integrations.gemini import GeminiFeedbackService
from fastapi.testclient import TestClient


def test_reference_features_persist_across_service_instances(tmp_path: Path, monkeypatch):
    source = Path(__file__).resolve().parents[2] / "assets/songs/summer-day/vocals.wav"
    original = ScoringService(cache_root=tmp_path).prepare_reference(source)
    def should_not_compute(_):
        raise AssertionError("Persisted reference should not be re-analyzed")
    monkeypatch.setattr(ScoringService, "_pitch", staticmethod(should_not_compute))
    restored = ScoringService(cache_root=tmp_path).prepare_reference(source)
    assert restored.pitch.voiced_seconds == original.pitch.voiced_seconds
    assert restored.pitch.confidence == original.pitch.confidence
    assert restored.audio == pytest.approx(original.audio)


def test_grading_starts_after_upload_and_finalize_reuses_job(client, vocal_wav, monkeypatch):
    analysis = client.app.state.analysis_service
    submissions = []
    original = analysis.submit
    def tracked(song, artifact):
        job = original(song, artifact)
        submissions.append(job)
        return job
    monkeypatch.setattr(analysis, "submit", tracked)
    song = client.get("/api/songs").json()[0]
    session = client.post("/api/sessions", json={"playerNames": ["Singer"], "songId": song["id"]}).json()
    prefix = f"/api/sessions/{session['id']}"
    client.post(prefix + "/start")
    client.post(prefix + "/reference-complete")
    response = client.post(prefix + "/recordings", data={
        "playerId": session["players"][0]["id"], "mimeType": "audio/wav", "prerollMs": "0",
        "durationMs": "1200", "recordingStartPerfMs": "0", "clockSamplePerfMs": "0",
        "clockSampleAudioSec": "0", "plannedPlaybackAudioSec": "0"},
        files={"file": ("take.wav", vocal_wav, "audio/wav")})
    assert response.status_code == 200, response.text
    assert len(submissions) == 1
    submissions[0].future.result(timeout=30)
    assert client.get(prefix + "/analysis-progress").json()["percent"] == 100
    started = time.perf_counter()
    assert client.post(prefix + "/finalize").status_code == 200
    assert time.perf_counter() - started < .5
    assert len(submissions) == 1
    assert client.post(prefix + "/finalize").status_code == 200
    assert len(submissions) == 1


def test_cpu_slot_is_free_while_another_job_waits_for_feedback():
    feedback_entered, second_audio = threading.Event(), threading.Event()
    calls = []
    def prepare_player(path):
        calls.append(path)
        if len(calls) == 2:
            second_audio.set()
        return object()
    def analyze(**kwargs):
        return SimpleNamespace(score=Score(pitch=100, rhythm=100, lyrics=None, completion=100,
            technicalTotal=100, scoringProfile="partial_no_lyrics", confidence={}),
            evidence=PerformanceEvidence(durationMs=10000, referenceWaveform=[0], playerWaveform=[0],
                referencePitchMidi=[None], playerPitchMidi=[None]))
    def feedback(**kwargs):
        if not feedback_entered.is_set():
            feedback_entered.set()
            assert second_audio.wait(5), "Cloud feedback must not hold the CPU semaphore"
        return GeminiFeedbackService._fallback(kwargs["score"])
    service = AnalysisService(
        scoring=SimpleNamespace(prepare_player=prepare_player, prepare_reference=lambda _: object(), analyze=analyze),
        elevenlabs=SimpleNamespace(transcribe=lambda _: TranscriptResult(None, [], "unavailable")),
        gemini=SimpleNamespace(feedback=feedback), reference_path_resolver=Path, max_workers=1)
    song = SimpleNamespace(reference_vocal_path="reference.wav", expected_lyrics="test")
    artifact = AudioArtifact(10000, 0, False, "/mix.mp3", Path("player.wav"))
    try:
        first = service.submit(song, artifact)
        assert feedback_entered.wait(5)
        second = service.submit(song, artifact)
        first.future.result(timeout=5)
        second.future.result(timeout=5)
        assert first.progress()["percent"] == second.progress()["percent"] == 100
    finally:
        second_audio.set()
        service.close()


def test_runtime_warmup_does_not_make_provider_calls(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Warmup must not call external providers")
    from backend.app.integrations.elevenlabs import ElevenLabsService
    monkeypatch.setattr(ElevenLabsService, "transcribe", forbidden)
    monkeypatch.setattr(GeminiFeedbackService, "feedback", forbidden)
    settings = Settings(runtime_root=tmp_path / "runtime", warm_audio_runtime=True,
                        gemini_api_key=None, elevenlabs_api_key=None)
    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/api/health").status_code == 200
