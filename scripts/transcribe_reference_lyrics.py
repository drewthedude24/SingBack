#!/usr/bin/env python3
"""Transcribe every prepared reference vocal and update manifest lyric cues."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.config import Settings
from backend.app.integrations.elevenlabs import ElevenLabsService, TranscriptResult


MANIFEST_PATH = ROOT / "assets" / "songs" / "manifest.json"
MAX_WORDS_PER_LINE = 7
MAX_LINE_SECONDS = 4.2
LINE_BREAK_GAP_SECONDS = 0.65


def clean_transcript(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\[[^]]+]", "", text)).strip()


def lyric_lines(transcript: TranscriptResult, duration_ms: int) -> list[dict[str, int | str]]:
    words = transcript.words
    if not words:
        return [{"startMs": 0, "endMs": duration_ms, "text": transcript.text or ""}]

    groups: list[list[dict[str, float | str]]] = []
    current: list[dict[str, float | str]] = []
    for word in words:
        start = float(word["start"])
        end = float(word["end"])
        should_break = bool(current) and (
            len(current) >= MAX_WORDS_PER_LINE
            or start - float(current[-1]["end"]) >= LINE_BREAK_GAP_SECONDS
            or end - float(current[0]["start"]) >= MAX_LINE_SECONDS
        )
        if should_break:
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)

    boundaries = [0]
    for left, right in zip(groups, groups[1:]):
        midpoint_seconds = (float(left[-1]["end"]) + float(right[0]["start"])) / 2
        boundaries.append(max(boundaries[-1], min(duration_ms, round(midpoint_seconds * 1000))))
    boundaries.append(duration_ms)

    return [
        {
            "startMs": boundaries[index],
            "endMs": boundaries[index + 1],
            "text": " ".join(str(word["text"]).strip() for word in group).strip(),
        }
        for index, group in enumerate(groups)
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write successful transcripts and continuous word-timed cues to manifest.json.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=False)
    settings = Settings(repository_root=ROOT)
    service = ElevenLabsService(settings)
    if not service.configured:
        raise SystemExit("ELEVENLABS_API_KEY is not configured in the root .env file.")

    songs = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    updates: list[tuple[dict, TranscriptResult]] = []
    for song in songs:
        vocal_path = ROOT / song["referenceVocalPath"]
        transcript = service.transcribe(vocal_path)
        if transcript.source != "elevenlabs" or not transcript.text:
            raise SystemExit(f"Transcription failed for {song['id']}; manifest was not changed.")
        updates.append((song, transcript))
        print(f"{song['title']}: {transcript.text}")

    if not args.write:
        print("Dry run only. Re-run with --write to update the manifest.")
        return

    for song, transcript in updates:
        song["expectedLyrics"] = clean_transcript(transcript.text or "")
        song["lyricLines"] = lyric_lines(transcript, int(song["durationMs"]))
    MANIFEST_PATH.write_text(
        json.dumps(songs, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {MANIFEST_PATH.relative_to(ROOT)} with {len(updates)} transcripts.")


if __name__ == "__main__":
    main()
