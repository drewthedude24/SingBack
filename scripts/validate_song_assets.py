#!/usr/bin/env python3
"""Validate the prepared demo-song manifest and WAV assets."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "assets" / "songs" / "manifest.json"
EXPECTED_DURATION_MS = 10_000
EXPECTED_SAMPLE_RATE = 44_100
EXPECTED_CHANNELS = 2
EXPECTED_SAMPLE_WIDTH = 2


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def inspect_wav(path: Path) -> int:
    if not path.is_file():
        fail(f"missing asset: {path.relative_to(ROOT)}")

    with wave.open(str(path), "rb") as wav_file:
        if wav_file.getframerate() != EXPECTED_SAMPLE_RATE:
            fail(f"{path.name}: expected 44100 Hz")
        if wav_file.getnchannels() != EXPECTED_CHANNELS:
            fail(f"{path.name}: expected stereo audio")
        if wav_file.getsampwidth() != EXPECTED_SAMPLE_WIDTH:
            fail(f"{path.name}: expected 16-bit PCM")
        return round(wav_file.getnframes() * 1000 / wav_file.getframerate())


def main() -> None:
    songs = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if len(songs) != 5:
        fail(f"expected 5 songs, found {len(songs)}")

    seen_ids: set[str] = set()
    for song in songs:
        song_id = song["id"]
        if song_id in seen_ids:
            fail(f"duplicate song id: {song_id}")
        seen_ids.add(song_id)

        if song["durationMs"] != EXPECTED_DURATION_MS:
            fail(f"{song_id}: manifest duration must be 10000 ms")
        if len(song["expectedLyrics"].split()) > 10:
            fail(f"{song_id}: scoring phrase must contain at most 10 words")

        song_dir = ROOT / "assets" / "songs" / song_id
        for filename in ("full.wav", "instrumental.wav", "vocals.wav"):
            duration_ms = inspect_wav(song_dir / filename)
            if abs(duration_ms - EXPECTED_DURATION_MS) > 5:
                fail(f"{song_id}/{filename}: duration is {duration_ms} ms")

        print(f"OK {song_id}: 3 WAV files, 10.000 s, 44.1 kHz stereo PCM")


if __name__ == "__main__":
    main()
