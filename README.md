# SingBack

SingBack is a local multiplayer song-memory party game built for HackRice 16.
Players hear one ten-second clip a single time, then take turns singing it back
from memory over the same instrumental. Once every turn is done, the game
reveals each remix anonymously and scores how close it came to the original.

Unlike karaoke apps that grade you against a note chart, SingBack compares your
voice to the actual recorded vocal, so the feedback can tell you that you drifted
flat on the second phrase rather than just that you missed a note.

## Quickstart

Two terminals, from the repository root.

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. API docs are at <http://127.0.0.1:8000/docs>.

**API keys are optional.** Gemini and ElevenLabs both have local fallbacks, so a
full round completes with an empty `.env`. Keys add spoken host narration, lyric
transcription, and richer coaching text. They never affect the numeric scores.

## How a round works

1. Enter 1 to 4 player names.
2. SingBack draws a random prepared ten-second clip. Everyone hears it once,
   with the lyrics on screen.
3. Each player records in turn over the instrumental, passing one device around.
4. Every take is aligned, mixed, and scored in parallel.
5. Reveals stay locked until the last turn finishes, then play in randomized
   anonymous order.
6. Scores, waveform and pitch evidence, and AI coaching for each performance.

## Scoring

Every score is deterministic. The same audio always produces the same number.

| Component | Weight | How it is measured |
| --- | --- | --- |
| Pitch | 45% | Librosa pYIN extracts the fundamental frequency, converted to MIDI. Octave-sized offsets are removed so any vocal range can score well, but a wrong key still costs you. Dynamic Time Warping aligns the contours and mean semitone error becomes the score. |
| Rhythm | 25% | Onset detection finds note attacks. Intervals between onsets are compared with DTW, so device latency is not punished twice. |
| Lyrics | 20% | ElevenLabs Scribe transcribes the isolated vocal. Word-level edit distance against the expected lyrics gives a word error rate. |
| Completion | 10% | Voiced seconds in the take against the reference, penalized in both directions. |

If a component cannot be measured, its weight is redistributed and the result is
labelled as partial rather than presented as a full score. Every score ships with
diagnostics: mean pitch error in semitones, mean rhythm error in milliseconds,
onset counts, and word error rate.

**Gemini never touches a number.** Scores are computed before it is called, and
its response schema has no score field. It receives the finished measurements
plus both audio files and returns structured coaching text. If it fails, a
threshold-based fallback writes the feedback and the scores are unchanged.

## Timing

`performance.now()` and `AudioContext.currentTime` are separate clocks with
different origins, so one cannot be subtracted from the other. Each turn:

1. `MediaRecorder` starts and captures `performance.now()` in its start event.
2. Both clocks are sampled back to back.
3. The instrumental is scheduled about 500 ms ahead on the audio clock.
4. The derived preroll and both raw samples upload with the recording.

The backend trims that exact offset with FFmpeg before mixing the vocal against
the instrumental.

## Song catalog

`assets/songs/manifest.json` holds five ten-second excerpts from Pixabay, each
with `full.wav`, `instrumental.wav`, and `vocals.wav`. Stems are separated
offline with Demucs, which never runs during a round. Lyric text and timing are
generated once from the isolated reference stems with ElevenLabs Scribe.

Regenerate lyrics after changing a clip:

```bash
python scripts/transcribe_reference_lyrics.py --write
```

Validate the catalog:

```bash
python3 scripts/validate_song_assets.py
```

Sources and license terms are recorded in
[assets/songs/SOURCES.md](assets/songs/SOURCES.md).

## Stack

React, TypeScript, Vite, Web Audio, MediaRecorder on the client. FastAPI,
FFmpeg, Librosa, NumPy on the server. Gemini for grounded coaching text,
ElevenLabs for transcription and host narration.

## Known limits

Sessions live in memory, so a page refresh ends the round. Play is single device,
pass and play. The catalog is five prepared clips because Demucs cannot run
inside a request.
