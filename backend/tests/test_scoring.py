from pathlib import Path

from backend.app.scoring.service import ScoringService


def test_identical_take_scores_high() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    vocal = repository_root / "assets/songs/summer-day/vocals.wav"

    score = ScoringService().score(
        reference_vocal_path=vocal,
        player_vocal_path=vocal,
        expected_lyrics="summer sun keeps shining down",
        detected_lyrics="summer sun keeps shining down",
        transcript_source="elevenlabs",
    )

    assert score.scoring_profile == "full"
    assert score.pitch is not None and score.pitch >= 95
    assert score.rhythm is not None and score.rhythm >= 95
    assert score.lyrics == 100
    assert score.completion >= 95
    assert score.technical_total >= 95
