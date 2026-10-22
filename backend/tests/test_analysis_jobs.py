import time
from pathlib import Path

import pytest

from backend.app.scoring.service import ScoringService


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
