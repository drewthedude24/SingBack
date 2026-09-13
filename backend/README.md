# SingBack backend

The MVP backend is a FastAPI service with an in-memory game-session store and
filesystem-backed generated audio. Song assets remain in the repository-level
`assets/songs` catalog. Session media is generated under `runtime/sessions`,
which is ignored by Git.

## Run locally

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --reload --port 8000 --env-file .env
```

Then open <http://127.0.0.1:8000/docs> for the interactive API documentation.
The React development server at ports 5173 or 4173 is allowed by CORS.

## Test

```bash
pytest backend/tests
```

`imageio-ffmpeg` supplies a portable FFmpeg binary when `ffmpeg` is not already
installed. Set `FFMPEG_BIN` to an explicit binary if desired.

## AI and voice setup

Add `GEMINI_API_KEY` and `ELEVENLABS_API_KEY` to the local root `.env`. Do not
send keys in chat and do not commit `.env`; it is already ignored by Git. The
default Gemini model is `gemini-2.5-flash`. The default ElevenLabs settings use
Scribe v2, Flash v2.5 TTS, and the configured public voice ID.

Check the configuration without exposing any secret:

```bash
curl http://127.0.0.1:8000/api/health
```

The response reports `configured` or `unconfigured` for each provider. With no
keys, lyric scoring is marked unavailable and the other measured components are
reweighted; Gemini coaching becomes deterministic local coaching; narration is
returned as readable text without an audio URL.

The deterministic score weights are pitch 45%, rhythm 25%, lyric recall 20%,
and completion 10%. Librosa owns the numeric measurements. ElevenLabs Scribe
owns transcription, and Gemini receives the measured result plus vocal audio to
produce schema-validated feedback only.

## Frontend integration order

Use this sequence for one complete round:

1. `GET /api/songs`
2. `POST /api/sessions`
3. `POST /api/sessions/{id}/start`
4. Optionally fetch `GET /api/sessions/{id}/narration/listen` and play `audioUrl`.
5. Show `song.expectedLyrics` and play `song.fullMixUrl` once.
6. `POST /api/sessions/{id}/reference-complete`
7. Upload the active player's multipart recording to
   `POST /api/sessions/{id}/recordings`.
8. Between players, call `POST /api/sessions/{id}/next-player`; repeat the
   upload until its `nextPhase` is `PROCESSING`.
9. `POST /api/sessions/{id}/finalize`, then play all anonymous performances.
10. Send all played IDs to `POST /api/sessions/{id}/reveal-complete`.
11. Submit one vote per player to `POST /api/sessions/{id}/votes`.
12. Read `GET /api/sessions/{id}/results/final` and fetch narration cue `results`.

Valid narration cues are `listen`, `turn`, `processing`, and `results`. Every
narration response includes the exact `text`, optional `audioUrl`, and a `source`
of `elevenlabs` or `fallback`.

The OpenAPI schema at `/openapi.json` is the source for exact request and
response fields. All validation and game-state failures use the shared
`{"error": {"code", "message", "retryable", "details"}}` envelope.

Only generated `mix.mp3` files are exposed under `/media/sessions`. Raw uploads
and normalized vocals live under `runtime/private` and are not web-served.
