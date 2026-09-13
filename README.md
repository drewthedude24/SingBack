# SingBack

SingBack is a local multiplayer song-memory party game for HackRice 2026. Players hear one short clip, then take turns recreating it from memory over the same instrumental. After everyone finishes, the game reveals each remix and opens its measurable singing grade.

## Five-hour MVP

The current build targets one reliable 1-to-6-player round on one laptop:

1. Choose 1–6 players and enter their names.
2. Let SingBack randomly draw one prepared 10-second clip and hear it once.
3. Record each player over the instrumental.
4. Upload, align, and mix each vocal.
5. Reveal every remix only after all turns finish.
6. Play or skip reveals, then inspect deterministic scores, waveform/pitch evidence,
   and grounded AI feedback.

The live path uses React, TypeScript, Vite, FastAPI, MediaRecorder, Web Audio,
FFmpeg, Librosa, Gemini, and ElevenLabs. Gemini and ElevenLabs have local
fallbacks so an API failure cannot stop the demo.

The scoring pipeline keeps judging explainable: Librosa measures pitch contour,
rhythm, and completion; ElevenLabs Scribe supplies the detected lyric transcript;
and Gemini turns those fixed measurements plus the vocal audio into structured
coaching. Gemini cannot modify the numeric result. ElevenLabs also voices the
game host at important transitions.

## Planning documents

- [Five-hour sprint plan](docs/SPRINT_PLAN.md)
- [Integration contract](docs/INTEGRATION_CONTRACT.md)
- [Prepared demo-song sources](assets/songs/SOURCES.md)

## Prepared song catalog

`assets/songs/manifest.json` contains five ten-second Pixabay vocal excerpts.
Every song folder includes `full.wav`, `instrumental.wav`, and `vocals.wav`.
The stems are prepared offline with Demucs; Demucs is not part of the live demo
request path.

Validate the catalog before integrating it with the backend:

```bash
python3 scripts/validate_song_assets.py
```

See [backend setup](backend/README.md) for API-key configuration. Lyrics are
deliberately shown during listening and recording so first-time players know the
short phrase they are being asked to recreate.
