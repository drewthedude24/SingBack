from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from backend.app.integrations.elevenlabs import ElevenLabsService
from backend.app.integrations.gemini import GeminiFeedbackService
from backend.app.models import Feedback, PerformanceEvidence, Score, SongManifestEntry
from backend.app.scoring.service import ScoringService
from backend.app.services.audio_service import AudioArtifact


@dataclass(frozen=True)
class PerformanceAnalysis:
    score: Score
    feedback: Feedback
    detected_lyrics: str | None
    evidence: PerformanceEvidence


class AnalysisService:
    def __init__(
        self,
        scoring: ScoringService,
        elevenlabs: ElevenLabsService,
        gemini: GeminiFeedbackService,
        reference_path_resolver: Callable[[str], Path],
    ) -> None:
        self._scoring = scoring
        self._elevenlabs = elevenlabs
        self._gemini = gemini
        self._reference_path_resolver = reference_path_resolver

    def analyze_many(
        self, song: SongManifestEntry, artifacts: dict[str, AudioArtifact]
    ) -> dict[str, PerformanceAnalysis]:
        if not artifacts:
            return {}
        with ThreadPoolExecutor(max_workers=min(3, len(artifacts))) as executor:
            futures = {
                player_id: executor.submit(self._analyze_one, song, artifact)
                for player_id, artifact in artifacts.items()
            }
            return {player_id: future.result() for player_id, future in futures.items()}

    def _analyze_one(
        self, song: SongManifestEntry, artifact: AudioArtifact
    ) -> PerformanceAnalysis:
        reference_vocal_path = self._reference_path_resolver(
            song.reference_vocal_path
        )
        transcript = self._elevenlabs.transcribe(artifact.vocal_path)
        scoring_result = self._scoring.analyze(
            reference_vocal_path=reference_vocal_path,
            player_vocal_path=artifact.vocal_path,
            expected_lyrics=song.expected_lyrics,
            detected_lyrics=transcript.text,
            transcript_source=transcript.source,
        )
        feedback = self._gemini.feedback(
            score=scoring_result.score,
            expected_lyrics=song.expected_lyrics,
            detected_lyrics=transcript.text,
            vocal_path=artifact.vocal_path,
            reference_vocal_path=reference_vocal_path,
        )
        return PerformanceAnalysis(
            score=scoring_result.score,
            feedback=feedback,
            detected_lyrics=transcript.text,
            evidence=scoring_result.evidence,
        )
