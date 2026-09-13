from __future__ import annotations

import random
import threading
from collections import Counter
from dataclasses import dataclass, field
from uuid import uuid4

from backend.app.errors import ApiError
from backend.app.models import (
    Feedback,
    FinalPerformance,
    FinalResults,
    NarrationCue,
    Phase,
    PlayerPublic,
    RecordingResponse,
    RevealPerformance,
    RevealResults,
    Score,
    SessionSong,
    SessionView,
    SongManifestEntry,
    VoteResponse,
)
from backend.app.services.audio_service import AudioArtifact
from backend.app.services.analysis_service import AnalysisService, PerformanceAnalysis
from backend.app.services.song_catalog import SongCatalog


@dataclass
class RecordingState:
    id: str
    player_id: str
    artifact: AudioArtifact
    analysis: PerformanceAnalysis | None = None


@dataclass
class SessionState:
    id: str
    song: SongManifestEntry
    players: list[PlayerPublic]
    phase: Phase = Phase.LOBBY
    current_player_index: int = 0
    recordings: dict[str, RecordingState] = field(default_factory=dict)
    reveal_order: list[str] = field(default_factory=list)
    acknowledged_reveals: set[str] = field(default_factory=set)
    votes: dict[str, str] = field(default_factory=dict)


class SessionService:
    def __init__(
        self, song_catalog: SongCatalog, analysis_service: AnalysisService
    ) -> None:
        self._song_catalog = song_catalog
        self._analysis_service = analysis_service
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def create(self, player_names: list[str], song_id: str) -> SessionView:
        song = self._song_catalog.get(song_id)
        if not self._song_catalog.is_ready(song):
            raise ApiError(
                409, "SONG_NOT_READY", "The selected song assets are incomplete."
            )
        state = SessionState(
            id=str(uuid4()),
            song=song,
            players=[
                PlayerPublic(id=str(uuid4()), displayName=name, turnOrder=index)
                for index, name in enumerate(player_names)
            ],
        )
        with self._lock:
            self._sessions[state.id] = state
        return self.view(state)

    def get(self, session_id: str) -> SessionState:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise ApiError(
                404, "SESSION_NOT_FOUND", "The game session does not exist."
            ) from exc

    def transition(
        self, session_id: str, expected: Phase, target: Phase
    ) -> SessionView:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, expected)
            state.phase = target
            return self.view(state)

    def active_player(self, session_id: str, player_id: str) -> SessionState:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.TURN_INTRO)
            current_player = state.players[state.current_player_index]
            if current_player.id != player_id:
                raise ApiError(
                    409,
                    "WRONG_PLAYER_TURN",
                    "The recording does not belong to the active player.",
                )
            if player_id in state.recordings:
                raise ApiError(
                    409, "DUPLICATE_RECORDING", "This player already has a recording."
                )
            return state

    def add_recording(
        self, session_id: str, player_id: str, artifact: AudioArtifact
    ) -> RecordingResponse:
        with self._lock:
            state = self.get(session_id)
            recording = RecordingState(
                id=str(uuid4()), player_id=player_id, artifact=artifact
            )
            state.recordings[player_id] = recording
            if len(state.recordings) == len(state.players):
                state.phase = Phase.PROCESSING
            else:
                state.phase = Phase.NEXT_PLAYER
            return RecordingResponse(
                recordingId=recording.id,
                status="ready",
                rawUrl=None,
                mixUrl=artifact.mix_url,
                detectedDurationMs=artifact.detected_duration_ms,
                appliedOffsetMs=artifact.applied_offset_ms,
                silent=artifact.silent,
                nextPhase=state.phase,
            )

    def advance_player(self, session_id: str) -> SessionView:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.NEXT_PLAYER)
            state.current_player_index += 1
            state.phase = Phase.TURN_INTRO
            return self.view(state)

    def finalize(self, session_id: str) -> RevealResults:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.PROCESSING)
            if len(state.recordings) != len(state.players):
                raise ApiError(
                    409, "ARTIFACTS_NOT_READY", "Every player must upload a recording."
                )
            artifacts = {
                player_id: recording.artifact
                for player_id, recording in state.recordings.items()
            }

        analyses = self._analysis_service.analyze_many(state.song, artifacts)

        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.PROCESSING)
            for player_id, analysis in analyses.items():
                state.recordings[player_id].analysis = analysis
            state.reveal_order = [player.id for player in state.players]
            random.SystemRandom().shuffle(state.reveal_order)
            state.phase = Phase.REVEAL
            return self.reveal_results(state)

    def reveal_results(self, state: SessionState) -> RevealResults:
        if state.phase is not Phase.REVEAL:
            raise ApiError(
                409, "RESULTS_NOT_READY", "Results remain hidden until reveal."
            )
        return RevealResults(
            sessionId=state.id,
            phase=state.phase,
            performances=[
                self._reveal_performance(state, player_id)
                for player_id in state.reveal_order
            ],
        )

    def complete_reveal(self, session_id: str, reveal_ids: list[str]) -> SessionView:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.REVEAL)
            expected = {
                self._reveal_id(index) for index in range(len(state.reveal_order))
            }
            if set(reveal_ids) != expected or len(reveal_ids) != len(expected):
                raise ApiError(
                    409,
                    "REVEALS_INCOMPLETE",
                    "Acknowledge every revealed performance exactly once.",
                )
            state.acknowledged_reveals = expected
            state.phase = Phase.VOTING
            return self.view(state)

    def vote(
        self, session_id: str, voter_player_id: str, target_reveal_id: str
    ) -> VoteResponse:
        with self._lock:
            state = self.get(session_id)
            self._require_phase(state, Phase.VOTING)
            player_ids = {player.id for player in state.players}
            if voter_player_id not in player_ids:
                raise ApiError(
                    404, "PLAYER_NOT_FOUND", "The voting player does not exist."
                )
            if voter_player_id in state.votes:
                raise ApiError(409, "DUPLICATE_VOTE", "This player has already voted.")
            target_player_id = self._player_id_for_reveal(state, target_reveal_id)
            if voter_player_id == target_player_id:
                raise ApiError(409, "SELF_VOTE", "Players cannot vote for themselves.")
            state.votes[voter_player_id] = target_player_id
            if len(state.votes) == len(state.players):
                state.phase = Phase.RESULTS
            return VoteResponse(
                accepted=True,
                votesReceived=len(state.votes),
                votesRequired=len(state.players),
                phase=state.phase,
            )

    def final_results(self, session_id: str) -> FinalResults:
        state = self.get(session_id)
        self._require_phase(state, Phase.RESULTS)
        vote_counts = Counter(state.votes.values())
        performances: list[FinalPerformance] = []
        for index, player_id in enumerate(state.reveal_order):
            reveal = self._reveal_performance(state, player_id)
            player = next(player for player in state.players if player.id == player_id)
            performances.append(
                FinalPerformance(
                    **reveal.model_dump(by_alias=True),
                    playerId=player.id,
                    displayName=player.display_name,
                    votes=vote_counts[player_id],
                )
            )
        technical_winner = max(
            state.players,
            key=lambda player: (
                self._score_for(state.recordings[player.id]).technical_total
            ),
        )
        crowd_favorite = max(
            state.players,
            key=lambda player: (vote_counts[player.id], -player.turn_order),
        )
        return FinalResults(
            sessionId=state.id,
            phase=state.phase,
            performances=performances,
            technicalWinnerPlayerId=technical_winner.id,
            crowdFavoritePlayerId=crowd_favorite.id,
        )

    def narration_text(self, session_id: str, cue: NarrationCue) -> str:
        state = self.get(session_id)
        if cue is NarrationCue.LISTEN:
            return (
                f"Listen closely to {state.song.title}. "
                "You get one play, then you sing it back."
            )
        if cue is NarrationCue.TURN:
            player = state.players[state.current_player_index]
            return f"{player.display_name}, take the stage. Your memory remix starts now."
        if cue is NarrationCue.PROCESSING:
            return "All performances are in. The SingBack table is calculating the reveal."
        if cue is NarrationCue.RESULTS:
            self._require_phase(state, Phase.RESULTS)
            final = self.final_results(session_id)
            winner = next(
                player
                for player in state.players
                if player.id == final.technical_winner_player_id
            )
            crowd = next(
                player
                for player in state.players
                if player.id == final.crowd_favorite_player_id
            )
            return (
                f"{winner.display_name} wins the technical crown. "
                f"{crowd.display_name} is the crowd favorite."
            )
        raise ApiError(400, "INVALID_NARRATION_CUE", "The narration cue is unknown.")

    def view(self, state: SessionState) -> SessionView:
        current_player_id = None
        if state.phase not in {Phase.REVEAL, Phase.VOTING, Phase.RESULTS}:
            current_player_id = state.players[state.current_player_index].id
        return SessionView(
            id=state.id,
            phase=state.phase,
            song=SessionSong(
                id=state.song.id,
                title=state.song.title,
                durationMs=state.song.duration_ms,
                fullMixUrl=state.song.full_mix_url,
                instrumentalUrl=f"/media/songs/{state.song.id}/instrumental.wav",
                expectedLyrics=state.song.expected_lyrics,
            ),
            players=state.players,
            currentPlayerId=current_player_id,
            allArtifactsReady=len(state.recordings) == len(state.players),
        )

    def _reveal_performance(
        self, state: SessionState, player_id: str
    ) -> RevealPerformance:
        index = state.reveal_order.index(player_id)
        recording = state.recordings[player_id]
        return RevealPerformance(
            revealId=self._reveal_id(index),
            mixUrl=recording.artifact.mix_url,
            score=self._score_for(recording),
            feedback=self._feedback_for(recording),
            detectedLyrics=(
                recording.analysis.detected_lyrics if recording.analysis else None
            ),
        )

    @staticmethod
    def _score_for(recording: RecordingState) -> Score:
        if recording.analysis:
            return recording.analysis.score
        completion = 0.0 if recording.artifact.silent else 100.0
        return Score(
            pitch=None,
            rhythm=None,
            lyrics=None,
            completion=completion,
            technicalTotal=completion,
            scoringProfile="completion_only",
            confidence={
                "pitch": "unavailable",
                "rhythm": "unavailable",
                "lyrics": "unavailable",
                "completion": "ok",
            },
            diagnostics={"analysisStatus": "not_finalized"},
        )

    @staticmethod
    def _feedback_for(recording: RecordingState) -> Feedback:
        if recording.analysis:
            return recording.analysis.feedback
        if recording.artifact.silent:
            return Feedback(
                summary="No clear vocal was detected.",
                strength="The turn completed successfully.",
                improvement="Move closer to the microphone and sing more loudly.",
                announcerLine="A mysterious performance entered the memory challenge.",
                tags=["low signal"],
                source="fallback",
            )
        return Feedback(
            summary="Your vocal was captured and mixed successfully.",
            strength="The performance contained a clear vocal signal.",
            improvement="Detailed pitch and rhythm analysis is coming next.",
            announcerLine="This memory remix made it safely to the stage.",
            tags=["complete take"],
            source="fallback",
        )

    @staticmethod
    def _require_phase(state: SessionState, expected: Phase) -> None:
        if state.phase is not expected:
            raise ApiError(
                409,
                "INVALID_SESSION_PHASE",
                f"Expected phase {expected.value}, but the session is {state.phase.value}.",
                details={"expected": expected.value, "actual": state.phase.value},
            )

    @staticmethod
    def _reveal_id(index: int) -> str:
        return f"reveal_{index + 1}"

    @staticmethod
    def _player_id_for_reveal(state: SessionState, target_reveal_id: str) -> str:
        if not target_reveal_id.startswith("reveal_"):
            raise ApiError(404, "REVEAL_NOT_FOUND", "The reveal entry does not exist.")
        try:
            index = int(target_reveal_id.removeprefix("reveal_")) - 1
            if index < 0:
                raise IndexError
            return state.reveal_order[index]
        except (ValueError, IndexError) as exc:
            raise ApiError(
                404, "REVEAL_NOT_FOUND", "The reveal entry does not exist."
            ) from exc
