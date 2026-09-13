from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np

from backend.app.models import Score


SAMPLE_RATE = 22_050
HOP_LENGTH = 256
SCORE_WEIGHTS = {
    "pitch": 0.45,
    "rhythm": 0.25,
    "lyrics": 0.20,
    "completion": 0.10,
}


@dataclass(frozen=True)
class PitchAnalysis:
    contour: np.ndarray | None
    confidence: str
    voiced_seconds: float
    mean_error_semitones: float | None


@dataclass(frozen=True)
class RhythmAnalysis:
    score: float | None
    confidence: str
    mean_error_ms: float | None
    onset_count: int


class ScoringService:
    """Compute repeatable metrics; no generative model can modify these values."""

    def score(
        self,
        *,
        reference_vocal_path: Path,
        player_vocal_path: Path,
        expected_lyrics: str,
        detected_lyrics: str | None,
        transcript_source: str,
    ) -> Score:
        reference = self._load(reference_vocal_path)
        player = self._load(player_vocal_path)

        reference_pitch = self._pitch(reference)
        player_pitch = self._pitch(player)
        pitch_score, pitch_confidence, pitch_error = self._compare_pitch(
            reference_pitch, player_pitch
        )

        reference_rhythm = self._onsets(reference)
        player_rhythm = self._onsets(player)
        rhythm_score, rhythm_confidence, rhythm_error = self._compare_rhythm(
            reference_rhythm, player_rhythm
        )

        completion_score = self._completion(
            reference_pitch.voiced_seconds, player_pitch.voiced_seconds
        )
        lyrics_score, lyric_error = self._lyric_score(
            expected_lyrics, detected_lyrics
        )

        components = {
            "pitch": pitch_score,
            "rhythm": rhythm_score,
            "lyrics": lyrics_score,
            "completion": completion_score,
        }
        available_weight = sum(
            SCORE_WEIGHTS[name]
            for name, value in components.items()
            if value is not None
        )
        technical_total = (
            sum(
                SCORE_WEIGHTS[name] * value
                for name, value in components.items()
                if value is not None
            )
            / available_weight
            if available_weight
            else 0.0
        )
        scoring_profile = (
            "full"
            if all(value is not None for value in components.values())
            else "partial_no_lyrics"
            if lyrics_score is None
            else "partial"
        )

        return Score(
            pitch=self._rounded(pitch_score),
            rhythm=self._rounded(rhythm_score),
            lyrics=self._rounded(lyrics_score),
            completion=self._rounded(completion_score) or 0.0,
            technicalTotal=self._rounded(technical_total) or 0.0,
            scoringProfile=scoring_profile,
            confidence={
                "pitch": pitch_confidence,
                "rhythm": rhythm_confidence,
                "lyrics": "ok" if lyrics_score is not None else "unavailable",
                "completion": (
                    "ok" if reference_pitch.voiced_seconds > 0 else "unavailable"
                ),
            },
            diagnostics={
                "pitchMeanErrorSemitones": self._rounded(pitch_error),
                "rhythmMeanErrorMs": self._rounded(rhythm_error),
                "referenceVoicedSeconds": self._rounded(
                    reference_pitch.voiced_seconds
                ),
                "playerVoicedSeconds": self._rounded(player_pitch.voiced_seconds),
                "referenceOnsetCount": len(reference_rhythm),
                "playerOnsetCount": len(player_rhythm),
                "lyricWordErrorRate": self._rounded(lyric_error),
                "transcriptSource": transcript_source,
            },
        )

    @staticmethod
    def _load(path: Path) -> np.ndarray:
        audio, _ = librosa.load(path, sr=SAMPLE_RATE, mono=True, duration=10.0)
        return np.nan_to_num(audio.astype(np.float32), copy=False)

    @staticmethod
    def _pitch(audio: np.ndarray) -> PitchAnalysis:
        if audio.size == 0 or float(np.max(np.abs(audio))) < 1e-4:
            return PitchAnalysis(None, "silent", 0.0, None)
        f0, voiced, voiced_probability = librosa.pyin(
            audio,
            fmin=float(librosa.note_to_hz("C2")),
            fmax=float(librosa.note_to_hz("C7")),
            sr=SAMPLE_RATE,
            frame_length=2048,
            hop_length=HOP_LENGTH,
        )
        valid = voiced & np.isfinite(f0)
        valid_count = int(np.count_nonzero(valid))
        voiced_seconds = valid_count * HOP_LENGTH / SAMPLE_RATE
        if valid_count < 8:
            return PitchAnalysis(None, "insufficient_voiced_audio", voiced_seconds, None)
        midi = librosa.hz_to_midi(f0[valid])
        probability = float(np.nanmedian(voiced_probability[valid]))
        confidence = "ok" if probability >= 0.55 and valid_count >= 20 else "low"
        return PitchAnalysis(
            contour=midi.astype(float),
            confidence=confidence,
            voiced_seconds=voiced_seconds,
            mean_error_semitones=None,
        )

    @staticmethod
    def _compare_pitch(
        reference: PitchAnalysis, player: PitchAnalysis
    ) -> tuple[float | None, str, float | None]:
        if not isinstance(reference.contour, np.ndarray) or not isinstance(
            player.contour, np.ndarray
        ):
            confidence = (
                player.confidence
                if player.confidence != "ok"
                else reference.confidence
            )
            return None, confidence, None
        # Treat octave-equivalent singing as valid for different vocal ranges,
        # but retain all other register/key error. The previous median-centering
        # made a melody sung in any wrong key score as perfect.
        pitch_offset = float(np.median(player.contour) - np.median(reference.contour))
        octave_adjustment = round(pitch_offset / 12.0) * 12.0
        reference_contour = reference.contour
        player_contour = player.contour - octave_adjustment
        cost = np.abs(reference_contour[:, None] - player_contour[None, :])
        _, path = librosa.sequence.dtw(C=cost, backtrack=True)
        mean_error = float(np.mean(cost[path[:, 0], path[:, 1]]))
        score = float(np.clip(100.0 - 10.0 * mean_error, 0.0, 100.0))
        confidence = (
            "ok"
            if reference.confidence == "ok" and player.confidence == "ok"
            else "low"
        )
        return score, confidence, mean_error

    @staticmethod
    def _onsets(audio: np.ndarray) -> np.ndarray:
        envelope = librosa.onset.onset_strength(
            y=audio, sr=SAMPLE_RATE, hop_length=HOP_LENGTH
        )
        return librosa.onset.onset_detect(
            onset_envelope=envelope,
            sr=SAMPLE_RATE,
            hop_length=HOP_LENGTH,
            units="time",
            backtrack=False,
        ).astype(float)

    @staticmethod
    def _compare_rhythm(
        reference: np.ndarray, player: np.ndarray
    ) -> tuple[float | None, str, float | None]:
        if len(reference) < 2 or len(player) < 2:
            return None, "insufficient_onsets", None
        # Compare the spacing between phrases rather than absolute onset time;
        # this avoids punishing a small recording-device latency twice.
        reference_intervals = np.diff(reference)
        player_intervals = np.diff(player)
        cost = np.abs(reference_intervals[:, None] - player_intervals[None, :])
        _, path = librosa.sequence.dtw(C=cost, backtrack=True)
        mean_error_seconds = float(np.mean(cost[path[:, 0], path[:, 1]]))
        coverage = min(len(reference), len(player)) / max(len(reference), len(player))
        score = float(
            np.clip(100.0 * math.exp(-mean_error_seconds / 0.4) * coverage, 0, 100)
        )
        confidence = "ok" if len(reference) >= 3 and len(player) >= 3 else "low"
        return score, confidence, mean_error_seconds * 1000

    @staticmethod
    def _completion(reference_seconds: float, player_seconds: float) -> float:
        if reference_seconds <= 0:
            return 0.0
        ratio = max(player_seconds / reference_seconds, 1e-6)
        return float(np.clip(100.0 * min(ratio, 1.0 / ratio), 0, 100))

    @classmethod
    def _lyric_score(
        cls, expected: str, detected: str | None
    ) -> tuple[float | None, float | None]:
        if not detected or not detected.strip():
            return None, None
        expected_tokens = cls._tokens(expected)
        detected_tokens = cls._tokens(detected)
        if not expected_tokens:
            return None, None
        distance = cls._edit_distance(expected_tokens, detected_tokens)
        word_error_rate = distance / len(expected_tokens)
        return max(0.0, 100.0 * (1.0 - word_error_rate)), word_error_rate

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z0-9']+", text.casefold())

    @staticmethod
    def _edit_distance(left: list[str], right: list[str]) -> int:
        previous = list(range(len(right) + 1))
        for left_index, left_word in enumerate(left, start=1):
            current = [left_index]
            for right_index, right_word in enumerate(right, start=1):
                current.append(
                    min(
                        current[-1] + 1,
                        previous[right_index] + 1,
                        previous[right_index - 1] + (left_word != right_word),
                    )
                )
            previous = current
        return previous[-1]

    @staticmethod
    def _rounded(value: float | None) -> float | None:
        if value is None or not math.isfinite(value):
            return None
        return round(value, 2)
