from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class Phase(StrEnum):
    LOBBY = "LOBBY"
    LISTEN = "LISTEN"
    TURN_INTRO = "TURN_INTRO"
    NEXT_PLAYER = "NEXT_PLAYER"
    PROCESSING = "PROCESSING"
    REVEAL = "REVEAL"
    RESULTS = "RESULTS"


class LyricLine(ApiModel):
    start_ms: int = Field(alias="startMs", ge=0)
    end_ms: int = Field(alias="endMs", gt=0)
    text: str


class SongManifestEntry(ApiModel):
    id: str
    title: str
    artist: str
    license_name: str = Field(alias="licenseName")
    license_url: str = Field(alias="licenseUrl")
    source_url: str = Field(alias="sourceUrl")
    source_view_count: int = Field(alias="sourceViewCount")
    clip_start_ms: int = Field(alias="clipStartMs")
    duration_ms: int = Field(alias="durationMs")
    full_mix_url: str = Field(alias="fullMixUrl")
    instrumental_path: str = Field(alias="instrumentalPath")
    reference_vocal_path: str = Field(alias="referenceVocalPath")
    expected_lyrics: str = Field(alias="expectedLyrics")
    lyric_lines: list[LyricLine] = Field(alias="lyricLines", default_factory=list)
    bpm: float | None = None
    key: str | None = None


class SongPublic(ApiModel):
    id: str
    title: str
    artist: str
    duration_ms: int = Field(alias="durationMs")
    full_mix_url: str = Field(alias="fullMixUrl")
    instrumental_url: str = Field(alias="instrumentalUrl")
    reference_vocal_url: str = Field(alias="referenceVocalUrl")
    expected_lyrics: str = Field(alias="expectedLyrics")
    lyric_lines: list[LyricLine] = Field(alias="lyricLines")
    ready: bool


class SessionSong(ApiModel):
    id: str
    title: str
    duration_ms: int = Field(alias="durationMs")
    full_mix_url: str = Field(alias="fullMixUrl")
    instrumental_url: str = Field(alias="instrumentalUrl")
    reference_vocal_url: str = Field(alias="referenceVocalUrl")
    expected_lyrics: str = Field(alias="expectedLyrics")
    lyric_lines: list[LyricLine] = Field(alias="lyricLines")


class PlayerPublic(ApiModel):
    id: str
    display_name: str = Field(alias="displayName")
    turn_order: int = Field(alias="turnOrder")


class CreateSessionRequest(ApiModel):
    player_names: list[str] = Field(alias="playerNames", min_length=1, max_length=4)
    song_id: str = Field(alias="songId")

    @field_validator("player_names")
    @classmethod
    def validate_player_names(cls, value: list[str]) -> list[str]:
        normalized = [name.strip() for name in value]
        if any(not name or len(name) > 30 for name in normalized):
            raise ValueError("player names must contain 1 to 30 characters")
        if len({name.casefold() for name in normalized}) != len(normalized):
            raise ValueError("player names must be unique")
        return normalized


class SessionView(ApiModel):
    id: str
    phase: Phase
    song: SessionSong
    players: list[PlayerPublic]
    current_player_id: str | None = Field(alias="currentPlayerId")
    all_artifacts_ready: bool = Field(alias="allArtifactsReady")


class RecordingResponse(ApiModel):
    recording_id: str = Field(alias="recordingId")
    status: str
    raw_url: str | None = Field(alias="rawUrl")
    mix_url: str = Field(alias="mixUrl")
    detected_duration_ms: int = Field(alias="detectedDurationMs")
    applied_offset_ms: int = Field(alias="appliedOffsetMs")
    silent: bool
    next_phase: Phase = Field(alias="nextPhase")


class Score(ApiModel):
    pitch: float | None
    rhythm: float | None
    lyrics: float | None
    completion: float
    technical_total: float = Field(alias="technicalTotal")
    scoring_profile: str = Field(alias="scoringProfile")
    confidence: dict[str, str]
    diagnostics: dict[str, float | int | str | None] = Field(default_factory=dict)


class Feedback(ApiModel):
    summary: str = Field(max_length=120)
    strength: str = Field(max_length=100)
    improvement: str = Field(max_length=100)
    announcer_line: str = Field(alias="announcerLine", max_length=140)
    tags: list[str] = Field(max_length=3)
    source: Literal["gemini", "fallback"]


class PerformanceEvidence(ApiModel):
    duration_ms: int = Field(alias="durationMs", gt=0)
    reference_waveform: list[float] = Field(alias="referenceWaveform")
    player_waveform: list[float] = Field(alias="playerWaveform")
    reference_pitch_midi: list[float | None] = Field(alias="referencePitchMidi")
    player_pitch_midi: list[float | None] = Field(alias="playerPitchMidi")


class RevealPerformance(ApiModel):
    reveal_id: str = Field(alias="revealId")
    mix_url: str = Field(alias="mixUrl")
    score: Score
    feedback: Feedback
    detected_lyrics: str | None = Field(alias="detectedLyrics")
    evidence: PerformanceEvidence | None = None


class RevealResults(ApiModel):
    session_id: str = Field(alias="sessionId")
    phase: Phase
    performances: list[RevealPerformance]


class RevealCompleteRequest(ApiModel):
    reveal_ids: list[str] = Field(alias="revealIds")


class FinalPerformance(RevealPerformance):
    player_id: str = Field(alias="playerId")
    display_name: str = Field(alias="displayName")


class FinalResults(ApiModel):
    session_id: str = Field(alias="sessionId")
    phase: Phase
    performances: list[FinalPerformance]
    technical_winner_player_id: str = Field(alias="technicalWinnerPlayerId")


class NarrationCue(StrEnum):
    LISTEN = "listen"
    TURN = "turn"
    PROCESSING = "processing"
    RESULTS = "results"


class NarrationResponse(ApiModel):
    cue: NarrationCue
    text: str
    audio_url: str | None = Field(alias="audioUrl")
    source: Literal["elevenlabs", "fallback"]
