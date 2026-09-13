from pathlib import Path

import numpy as np
import pytest

from backend.app.scoring.service import PitchAnalysis, ScoringService


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


def test_pitch_comparison_allows_octaves_but_penalizes_wrong_key() -> None:
    reference = PitchAnalysis(
        contour=np.array([60.0, 62.0, 64.0, 65.0, 67.0]),
        confidence="ok",
        voiced_seconds=1.0,
        mean_error_semitones=None,
    )
    octave_higher = PitchAnalysis(
        contour=np.array([72.0, 74.0, 76.0, 77.0, 79.0]),
        confidence="ok",
        voiced_seconds=1.0,
        mean_error_semitones=None,
    )
    wrong_key = PitchAnalysis(
        contour=np.array([62.0, 64.0, 66.0, 67.0, 69.0]),
        confidence="ok",
        voiced_seconds=1.0,
        mean_error_semitones=None,
    )

    octave_score, _, _ = ScoringService._compare_pitch(reference, octave_higher)
    wrong_key_score, _, _ = ScoringService._compare_pitch(reference, wrong_key)

    assert octave_score == 100
    assert wrong_key_score is not None and wrong_key_score < octave_score


def test_rhythm_comparison_ignores_constant_device_latency() -> None:
    reference = np.array([0.2, 0.8, 1.6, 2.1])
    delayed = reference + 0.35

    score, _, error_ms = ScoringService._compare_rhythm(reference, delayed)

    assert score == pytest.approx(100)
    assert error_ms == pytest.approx(0)
