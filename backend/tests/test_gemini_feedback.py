from pathlib import Path
from types import SimpleNamespace

from google import genai

from backend.app.config import Settings
from backend.app.integrations.gemini import GeminiFeedbackPayload, GeminiFeedbackService
from backend.app.models import Score


def test_long_valid_coaching_is_shortened_instead_of_discarded(tmp_path, monkeypatch):
    payload = GeminiFeedbackPayload(
        summary="Great melody recall. " * 12,
        strength="Your phrasing follows the reference. " * 8,
        improvement="Try a more confident final entrance. " * 8,
        announcer_line="The melody survived the memory test. " * 8,
        tags=["pitch", "rhythm", "phrasing", "extra tag"],
    )
    fake_client = SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda **kwargs: SimpleNamespace(parsed=payload),
    ))
    monkeypatch.setattr(genai, "Client", lambda **kwargs: fake_client)
    vocal = tmp_path / "vocal.wav"
    vocal.write_bytes(b"test fixture; model client is mocked")
    score = Score(
        pitch=80, rhythm=80, lyrics=80, completion=80, technicalTotal=80,
        scoringProfile="full", confidence={},
    )
    result = GeminiFeedbackService(Settings(gemini_api_key="test-only")).feedback(
        score=score, expected_lyrics="test", detected_lyrics="test",
        vocal_path=Path(vocal), reference_vocal_path=Path(vocal),
    )
    assert result.source == "gemini"
    assert len(result.summary) <= 120
    assert len(result.strength) <= 100
    assert len(result.improvement) <= 100
    assert len(result.announcer_line) <= 140
    assert len(result.tags) == 3
    assert score.technical_total == 80
