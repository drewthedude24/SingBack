# SingBack

SingBack is a local multiplayer song-memory party game for HackRice 2026. Players hear one short clip, then take turns recreating it from memory over the same instrumental. After everyone finishes, the game reveals the remixes, shows measurable singing scores, and collects a crowd vote.

## Five-hour MVP

The first build targets one reliable three-player round on one laptop:

1. Enter three player names.
2. Hear one prepared 10-second clip once.
3. Record each player over the instrumental.
4. Upload, align, and mix each vocal.
5. Reveal every remix only after all turns finish.
6. Show deterministic scores, grounded feedback, and crowd voting.

The live path uses React, TypeScript, Vite, FastAPI, SQLite, MediaRecorder, Web Audio, and FFmpeg. Gemini and ElevenLabs are optional integrations with local fallbacks so an API failure cannot stop the demo.

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

Implementation intentionally starts with one complete vertical slice before adding scoring sophistication, extra songs, or visual effects.
