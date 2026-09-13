from __future__ import annotations

import json
from pathlib import Path

from backend.app.errors import ApiError
from backend.app.models import SongManifestEntry, SongPublic


class SongCatalog:
    def __init__(self, manifest_path: Path, repository_root: Path) -> None:
        self._repository_root = repository_root
        try:
            raw_songs = json.loads(manifest_path.read_text(encoding="utf-8"))
            songs = [SongManifestEntry.model_validate(song) for song in raw_songs]
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Unable to load song manifest: {manifest_path}"
            ) from exc
        self._songs = {song.id: song for song in songs}

    def all_public(self) -> list[SongPublic]:
        return [self.to_public(song) for song in self._songs.values()]

    def get(self, song_id: str) -> SongManifestEntry:
        try:
            return self._songs[song_id]
        except KeyError as exc:
            raise ApiError(
                404, "SONG_NOT_FOUND", "The selected song does not exist."
            ) from exc

    def asset_path(self, relative_path: str) -> Path:
        candidate = (self._repository_root / relative_path).resolve()
        assets_root = (self._repository_root / "assets" / "songs").resolve()
        if not candidate.is_relative_to(assets_root):
            raise RuntimeError("Song manifest path escapes the song assets directory")
        return candidate

    def is_ready(self, song: SongManifestEntry) -> bool:
        full_mix_path = self.asset_path(f"assets/songs/{song.id}/full.wav")
        return all(
            path.is_file()
            for path in (
                full_mix_path,
                self.asset_path(song.instrumental_path),
                self.asset_path(song.reference_vocal_path),
            )
        )

    def to_public(self, song: SongManifestEntry) -> SongPublic:
        return SongPublic(
            id=song.id,
            title=song.title,
            artist=song.artist,
            durationMs=song.duration_ms,
            fullMixUrl=song.full_mix_url,
            instrumentalUrl=f"/media/songs/{song.id}/instrumental.wav",
            expectedLyrics=song.expected_lyrics,
            ready=self.is_ready(song),
        )
