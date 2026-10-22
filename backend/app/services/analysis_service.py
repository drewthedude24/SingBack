from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from threading import BoundedSemaphore, Lock
from time import perf_counter
from typing import Callable

from backend.app.integrations.elevenlabs import ElevenLabsService
from backend.app.integrations.gemini import GeminiFeedbackService
from backend.app.models import Feedback, PerformanceEvidence, Score, SongManifestEntry
from backend.app.scoring.service import ScoringService
from backend.app.services.audio_service import AudioArtifact
from backend.app.errors import ApiError


@dataclass(frozen=True)
class PerformanceAnalysis:
    score: Score
    feedback: Feedback
    detected_lyrics: str | None
    evidence: PerformanceEvidence


@dataclass
class AnalysisJob:
    future: Future[PerformanceAnalysis] | None = None
    completed: set[str] = field(default_factory=set)
    lock: Lock = field(default_factory=Lock)

    def mark(self, stage: str) -> None:
        with self.lock:
            self.completed.add(stage)

    def progress(self) -> dict:
        with self.lock:
            done = set(self.completed)
        if self.future is not None and self.future.done() and self.future.exception() is not None:
            return {"percent": 0, "stage": "error"}
        weights = {"started": 5, "audio": 60, "transcript": 20, "feedback": 15}
        percent = sum(weight for key, weight in weights.items() if key in done)
        stage = ("complete" if percent == 100 else "feedback" if {"audio", "transcript"} <= done
                 else "transcription" if "audio" in done else "audio" if "started" in done else "queued")
        return {"percent": percent, "stage": stage}


class AnalysisService:
    def __init__(
        self,
        scoring: ScoringService,
        elevenlabs: ElevenLabsService,
        gemini: GeminiFeedbackService,
        reference_path_resolver: Callable[[str], Path],
        max_workers: int = 4,
    ) -> None:
        self._scoring = scoring
        self._elevenlabs = elevenlabs
        self._gemini = gemini
        self._reference_path_resolver = reference_path_resolver
        self._max_workers = max(1, min(4, max_workers))
        self._worker_slots = BoundedSemaphore(self._max_workers)
        # Cloud requests can overlap even on a one-CPU-worker deployment. Only
        # local DSP holds the CPU slot; slow remote feedback cannot block it.
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="singback-grade")
        self._transcripts = ThreadPoolExecutor(max_workers=4, thread_name_prefix="singback-scribe")
        self._queue_slots = BoundedSemaphore(32)

    def submit(self, song: SongManifestEntry, artifact: AudioArtifact) -> AnalysisJob:
        if not self._queue_slots.acquire(blocking=False):
            raise ApiError(503, "ANALYSIS_BUSY", "The grading queue is full. Please retry shortly.", retryable=True)
        job = AnalysisJob()
        job.future = self._executor.submit(self._analyze_performance, song, artifact, job)
        job.future.add_done_callback(lambda _: self._queue_slots.release())
        return job

    def close(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)
        self._transcripts.shutdown(wait=True, cancel_futures=True)

    def analyze_many(
        self, song: SongManifestEntry, artifacts: dict[str, AudioArtifact]
    ) -> dict[str, PerformanceAnalysis]:
        if not artifacts:
            return {}
        jobs = {player_id: self.submit(song, artifact) for player_id, artifact in artifacts.items()}
        return {player_id: job.future.result() for player_id, job in jobs.items() if job.future is not None}

    def prewarm(self, song: SongManifestEntry) -> None:
        self._scoring.prewarm_reference(
            self._reference_path_resolver(song.reference_vocal_path)
        )

    def _analyze_performance(
        self, song: SongManifestEntry, artifact: AudioArtifact, job: AnalysisJob
    ) -> PerformanceAnalysis:
        analysis_started = perf_counter()
        reference_vocal_path = self._reference_path_resolver(
            song.reference_vocal_path
        )
        job.mark("started")
        def transcribe():
            started = perf_counter()
            transcript = self._elevenlabs.transcribe(artifact.vocal_path)
            job.mark("transcript")
            return transcript, round((perf_counter() - started) * 1000)

        transcript_future = self._transcripts.submit(transcribe)
        with self._worker_slots:
            local_started = perf_counter()
            # Extract the expensive signal features while Scribe is in flight;
            # combining the transcript with these features is inexpensive.
            player_features = self._scoring.prepare_player(artifact.vocal_path)
            reference_features = self._scoring.prepare_reference(reference_vocal_path)
            local_analysis_ms = round((perf_counter() - local_started) * 1000)
            job.mark("audio")
        transcript, transcription_ms = transcript_future.result()
        scoring_result = self._scoring.analyze(
            reference_vocal_path=reference_vocal_path, player_vocal_path=artifact.vocal_path,
            expected_lyrics=song.expected_lyrics, detected_lyrics=transcript.text,
            transcript_source=transcript.source, player_features=player_features,
            reference_features=reference_features,
        )
        scoring_result.score.diagnostics.update(
            {
                "transcriptionMs": transcription_ms,
                "localAnalysisMs": local_analysis_ms,
            }
        )
        gemini_started = perf_counter()
        feedback = self._gemini.feedback(
            score=scoring_result.score,
            expected_lyrics=song.expected_lyrics,
            detected_lyrics=transcript.text,
            vocal_path=artifact.vocal_path,
            reference_vocal_path=reference_vocal_path,
        )
        scoring_result.score.diagnostics.update(
            {
                "geminiFeedbackMs": round((perf_counter() - gemini_started) * 1000),
                "analysisWallMs": round((perf_counter() - analysis_started) * 1000),
            }
        )
        job.mark("feedback")
        return PerformanceAnalysis(
            score=scoring_result.score,
            feedback=feedback,
            detected_lyrics=transcript.text,
            evidence=scoring_result.evidence,
        )
