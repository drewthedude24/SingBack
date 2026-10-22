from typing import Literal

from pydantic import Field, field_validator

from backend.app.models import ApiModel, FinalResults, SessionSong


class RoomNameRequest(ApiModel):
    display_name: str = Field(alias="displayName", min_length=1, max_length=30)

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter your name")
        return value


class ReadyRequest(ApiModel):
    ready: bool


class RoomPlayer(ApiModel):
    id: str
    display_name: str = Field(alias="displayName")
    is_host: bool = Field(alias="isHost")
    ready: bool
    listened: bool
    connected: bool
    recorded: bool


class RoomProgressPlayer(ApiModel):
    player_id: str = Field(alias="playerId")
    display_name: str = Field(alias="displayName")
    percent: int
    stage: str


class RoomProgress(ApiModel):
    percent: int
    completed_players: int = Field(alias="completedPlayers")
    total_players: int = Field(alias="totalPlayers")
    players: list[RoomProgressPlayer]


class RoomView(ApiModel):
    code: str
    phase: Literal["LOBBY", "LISTEN", "TURN_INTRO", "PROCESSING", "RESULTS", "CLOSED"]
    round_number: int = Field(alias="roundNumber")
    me_id: str = Field(alias="meId")
    players: list[RoomPlayer]
    song: SessionSong | None
    current_player_id: str | None = Field(alias="currentPlayerId")
    progress: RoomProgress | None = None
    results: FinalResults | None = None
    error: str | None = None


class RoomCredentials(ApiModel):
    code: str
    token: str
    room: RoomView
