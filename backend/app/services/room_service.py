"""Single-instance, token-authenticated rooms sharing the existing game pipeline.

Room codes locate a lobby; random per-device tokens authorize actions. Internal
session IDs are deliberately not exposed, so legacy unauthenticated pass-and-play
routes cannot be used to control an online room.
"""
from __future__ import annotations

import io
import secrets
import threading
import time
import wave
from dataclasses import dataclass, field
from uuid import uuid4

from backend.app.errors import ApiError
from backend.app.models import FinalResults, Phase
from backend.app.room_models import RoomCredentials, RoomPlayer, RoomView
from backend.app.services.audio_service import AudioArtifact, AudioService
from backend.app.services.session_service import SessionService
from backend.app.services.song_catalog import SongCatalog

ROOM_LIFETIME_SECONDS = 6 * 60 * 60


@dataclass
class Participant:
    id: str
    name: str
    token: str
    ready: bool = False
    listened: bool = False
    last_seen: float = field(default_factory=time.monotonic)
    session_player_id: str | None = None
    uploading: bool = False


@dataclass
class Room:
    code: str
    host_id: str
    players: list[Participant]
    created_at: float = field(default_factory=time.monotonic)
    session_id: str | None = None
    round_number: int = 0
    closed: bool = False
    finalizing: bool = False
    error: str | None = None


class RoomService:
    def __init__(self, sessions: SessionService, catalog: SongCatalog, audio: AudioService) -> None:
        self._sessions, self._catalog, self._audio = sessions, catalog, audio
        self._rooms: dict[str, Room] = {}
        self._lock = threading.RLock()

    def create(self, name: str) -> RoomCredentials:
        with self._lock:
            now = time.monotonic()
            self._rooms = {code: room for code, room in self._rooms.items()
                           if now - room.created_at < ROOM_LIFETIME_SECONDS}
            if len(self._rooms) >= 100:
                raise ApiError(503, "ROOMS_BUSY", "The demo has too many active rooms. Please try later.", retryable=True)
            alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            while code in self._rooms:
                code = "".join(secrets.choice(alphabet) for _ in range(6))
            player = Participant(str(uuid4()), name, secrets.token_urlsafe(32))
            room = Room(code, player.id, [player])
            self._rooms[code] = room
            return RoomCredentials(code=code, token=player.token, room=self._view(room, player))

    def join(self, code: str, name: str) -> RoomCredentials:
        with self._lock:
            room = self._get(code)
            if room.closed or room.session_id:
                raise ApiError(409, "ROOM_STARTED", "This room has already started. Ask the host to play again.")
            if len(room.players) >= 4:
                raise ApiError(409, "ROOM_FULL", "This room already has four players.")
            if any(player.name.casefold() == name.casefold() for player in room.players):
                raise ApiError(409, "NAME_TAKEN", "That name is already in the room. Try a different name.")
            player = Participant(str(uuid4()), name, secrets.token_urlsafe(32))
            room.players.append(player)
            return RoomCredentials(code=room.code, token=player.token, room=self._view(room, player))

    def view(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token)
            return self._view(room, player)

    def ready(self, code: str, token: str, ready: bool) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token)
            if room.session_id or room.closed:
                raise ApiError(409, "ROOM_STARTED", "Readiness can only change in the lobby.")
            player.ready = ready
            return self._view(room, player)

    def start(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token, host=True)
            if room.closed or room.session_id:
                raise ApiError(409, "ROOM_STARTED", "This round has already started.")
            if len(room.players) < 2 or not all(p.ready for p in room.players):
                raise ApiError(409, "PLAYERS_NOT_READY", "At least two players must join and everyone must be ready.")
            songs = [song for song in self._catalog.all_public() if song.ready]
            if not songs:
                raise ApiError(409, "NO_SONGS", "No playable songs are available.")
            session = self._sessions.create([p.name for p in room.players], secrets.choice(songs).id, private=True)
            room.session_id = session.id
            room.round_number += 1
            room.error = None
            for participant, session_player in zip(room.players, session.players, strict=True):
                participant.session_player_id = session_player.id
                participant.listened = False
            self._sessions.transition(session.id, Phase.LOBBY, Phase.LISTEN)
            return self._view(room, player)

    def listened(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token)
            state = self._session(room)
            if state.phase is Phase.LISTEN:
                player.listened = True
                if all(p.listened for p in room.players):
                    self._sessions.transition(state.id, Phase.LISTEN, Phase.TURN_INTRO)
            elif not player.listened:
                raise ApiError(409, "WRONG_ROOM_PHASE", "The listening stage is over.")
            return self._view(room, player)

    def reserve_upload(self, code: str, token: str):
        with self._lock:
            room, player = self._authenticate(code, token)
            state = self._session(room)
            self._sessions.active_player(state.id, player.session_player_id)
            if player.uploading:
                raise ApiError(409, "UPLOAD_IN_PROGRESS", "Your recording is already uploading.")
            player.uploading = True
            return state.id, player.session_player_id, self._catalog.asset_path(state.song.instrumental_path)

    def cancel_upload(self, code: str, token: str) -> None:
        with self._lock:
            _, player = self._authenticate(code, token)
            player.uploading = False

    def finish_upload(self, code: str, token: str, artifact: AudioArtifact) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token)
            state = self._session(room)
            try:
                self._sessions.add_recording(state.id, player.session_player_id, artifact)
            finally:
                player.uploading = False
            if state.phase is Phase.NEXT_PLAYER:
                self._sessions.advance_player(state.id)
            if state.phase is Phase.PROCESSING:
                self._finalize_async(room)
            return self._view(room, player)

    def retry(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token, host=True)
            if self._session(room).phase is Phase.PROCESSING:
                self._finalize_async(room)
            return self._view(room, player)

    def rematch(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, player = self._authenticate(code, token, host=True)
            state = self._session(room)
            if state.phase is not Phase.RESULTS:
                raise ApiError(409, "ROUND_NOT_FINISHED", "Finish this round before starting another.")
            room.session_id = None
            for p in room.players:
                p.ready, p.listened, p.session_player_id = False, False, None
            return self._view(room, player)

    def remove(self, code: str, token: str, player_id: str) -> RoomView:
        with self._lock:
            room, host = self._authenticate(code, token, host=True)
            if room.session_id:
                raise ApiError(409, "ROOM_STARTED", "Players can only be removed in the lobby.")
            if player_id == host.id:
                raise ApiError(409, "HOST_REQUIRED", "The host cannot remove themselves.")
            room.players = [p for p in room.players if p.id != player_id]
            return self._view(room, host)

    def leave(self, code: str, token: str) -> None:
        with self._lock:
            room, player = self._authenticate(code, token)
            if player.id == room.host_id:
                room.closed = True
            elif not room.session_id:
                room.players.remove(player)
            else:
                # Keep a departed player in the turn order. The host can skip
                # them explicitly, rather than silently discarding a recording.
                player.last_seen = time.monotonic() - 60

    def skip(self, code: str, token: str) -> RoomView:
        with self._lock:
            room, host = self._authenticate(code, token, host=True)
            state = self._session(room)
            if state.phase is Phase.LISTEN:
                for p in room.players:
                    p.listened = True
                self._sessions.transition(state.id, Phase.LISTEN, Phase.TURN_INTRO)
                return self._view(room, host)
            self._sessions._require_phase(state, Phase.TURN_INTRO)
            active = next(p for p in room.players if p.session_player_id == self._sessions.view(state).current_player_id)
            if active.uploading:
                raise ApiError(409, "UPLOAD_IN_PROGRESS", "A recording is uploading. Wait before skipping.")
            active.uploading = True
            active_token = active.token
            session_id, player_id = state.id, active.session_player_id
            instrumental = self._catalog.asset_path(state.song.instrumental_path)
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(bytes(22050 * 2 * 10))
        try:
            artifact = self._audio.process_recording(session_id=session_id, player_id=player_id,
                upload_bytes=output.getvalue(), mime_type="audio/wav", instrumental_path=instrumental, preroll_ms=0)
            self.finish_upload(code, active_token, artifact)
        except Exception:
            self.cancel_upload(code, active_token)
            raise
        return self.view(code, token)

    def narration_text(self, code: str, token: str, cue) -> str:
        with self._lock:
            room, _ = self._authenticate(code, token)
            return self._sessions.narration_text(self._session(room).id, cue)

    def _finalize_async(self, room: Room) -> None:
        if room.finalizing:
            return
        room.finalizing, room.error = True, None
        def finalize():
            try:
                results = self._sessions.finalize(room.session_id)
                with self._lock:
                    self._sessions.complete_reveal(room.session_id, [p.reveal_id for p in results.performances])
            except Exception:
                with self._lock:
                    room.error = "Grading could not finish. The host can retry without re-recording."
            finally:
                with self._lock:
                    room.finalizing = False
        threading.Thread(target=finalize, daemon=True, name=f"room-finalize-{room.code}").start()

    def _get(self, code: str) -> Room:
        room = self._rooms.get(code.upper())
        if room is None or time.monotonic() - room.created_at > ROOM_LIFETIME_SECONDS:
            raise ApiError(404, "ROOM_NOT_FOUND", "Room not found or expired. Check the code, or create a new room.")
        return room

    def _authenticate(self, code: str, token: str, host: bool = False) -> tuple[Room, Participant]:
        room = self._get(code)
        player = next((p for p in room.players if secrets.compare_digest(p.token, token)), None)
        if player is None:
            raise ApiError(403, "ROOM_ACCESS_DENIED", "This device is not a member of the room. Join again.")
        if host and player.id != room.host_id:
            raise ApiError(403, "HOST_ONLY", "Only the host can do this.")
        player.last_seen = time.monotonic()
        return room, player

    def _session(self, room: Room):
        if room.closed:
            raise ApiError(409, "ROOM_CLOSED", "The host ended this room.")
        if room.session_id is None:
            raise ApiError(409, "ROUND_NOT_STARTED", "The host has not started the round.")
        return self._sessions.get(room.session_id)

    def _view(self, room: Room, me: Participant) -> RoomView:
        state = self._sessions.get(room.session_id) if room.session_id else None
        session = self._sessions.view(state) if state else None
        mapping = {p.session_player_id: p.id for p in room.players}
        progress = self._sessions.analysis_progress(state.id) if state else None
        if progress:
            for p in progress["players"]:
                p["playerId"] = mapping[p["playerId"]]
        results = None
        if state and state.phase is Phase.RESULTS:
            raw = self._sessions.final_results(state.id).model_dump(by_alias=True)
            raw["sessionId"] = room.code
            raw["technicalWinnerPlayerId"] = mapping[raw["technicalWinnerPlayerId"]]
            for p in raw["performances"]:
                p["playerId"] = mapping[p["playerId"]]
            results = FinalResults.model_validate(raw)
        # Media URLs use the session UUID, so strip it out of online URLs to
        # keep that UUID from enabling access through legacy session routes.
        if results:
            for p in results.performances:
                p.mix_url = p.mix_url.replace(f"/media/sessions/{state.id}/", f"/api/rooms/{room.code}/mixes/")
        return RoomView(code=room.code, phase="CLOSED" if room.closed else
                        "PROCESSING" if state and state.phase is Phase.REVEAL else state.phase.value if state else "LOBBY",
                        roundNumber=room.round_number, meId=me.id,
                        players=[RoomPlayer(id=p.id, displayName=p.name, isHost=p.id == room.host_id,
                            ready=p.ready, listened=p.listened, connected=time.monotonic()-p.last_seen < 20,
                            recorded=bool(state and p.session_player_id in state.recordings)) for p in room.players],
                        song=session.song if session else None,
                        currentPlayerId=mapping.get(session.current_player_id) if session else None,
                        progress=progress, results=results, error=room.error)

    def mix_path(self, code: str, player_id: str):
        # Opaque per-performance IDs make these as private as existing media
        # links. Reveal only after the whole round is complete.
        with self._lock:
            room = self._get(code)
            state = self._session(room)
            self._sessions._require_phase(state, Phase.RESULTS)
            if player_id not in state.recordings:
                raise ApiError(404, "PERFORMANCE_NOT_FOUND", "Performance not found.")
            return self._audio._settings.session_media_root / state.id / player_id / "mix.mp3"
