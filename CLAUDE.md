# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

SingBack is a local multiplayer song-memory party game built for HackRice 2026. Three players hear a 10-second clip once, then each records themselves singing it back over the same instrumental. The app reveals all three remixes only after every player has finished, shows deterministic scores, and runs a crowd vote.

The frozen five-hour MVP scope, checkpoints, and per-teammate ownership are defined in [docs/SPRINT_PLAN.md](docs/SPRINT_PLAN.md). The full API contract, game-phase state machine, error shape, and audio-timing rules are defined in [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md) — read that file before changing any endpoint, request/response shape, or phase transition.

**Current state**: `backend/` is implemented (FastAPI app, in-memory session store, FFmpeg pipeline, song catalog). `frontend/` does not yet contain a React app — it's an empty directory pending scaffolding.

## Commands

Backend (run from repository root, not `backend/`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

Interactive API docs: http://127.0.0.1:8000/docs

Run backend tests:

```bash
pytest backend/tests
```

Run a single test:

```bash
pytest backend/tests/test_session_flow.py::test_name
```

Validate the prepared song catalog (checks that each song folder has `full.wav`, `instrumental.wav`, `vocals.wav` matching `assets/songs/manifest.json`):

```bash
python3 scripts/validate_song_assets.py
```

Frontend (once scaffolded): a React + TypeScript + Vite app is expected to run on port 5173 or 4173 — both are pre-authorized in backend CORS config (`backend/app/config.py`).

## Architecture

### Backend is authoritative

The backend owns session phase, turn order, reveal readiness, scores, and vote validity. The frontend requests every phase change through the API and must never advance UI state (e.g. reveal, turn order) ahead of what the backend returns — this is a hard rule from the integration contract, not just a convention.

### Game phase state machine

```
LOBBY -> LISTEN -> TURN_INTRO -> COUNTDOWN -> RECORDING -> UPLOADING
UPLOADING -> NEXT_PLAYER -> TURN_INTRO   (repeats per player)
UPLOADING -> PROCESSING -> REVEAL -> VOTING -> RESULTS
```

`SessionService` (`backend/app/services/session_service.py`) is the single place that enforces phase transitions. Every mutating method calls `_require_phase` before changing `SessionState.phase`; invalid transitions raise `ApiError(409, "INVALID_SESSION_PHASE", ...)`. When adding a new transition, follow this same guard pattern rather than mutating `state.phase` directly from a route.

Session state is in-memory only (`dict[str, SessionState]` guarded by a `threading.RLock`), not persisted to SQLite yet despite the schema sketch in the integration contract — restarting the server drops all sessions.

### Request flow for one round

1. `GET /api/songs` → `POST /api/sessions` → `POST /api/sessions/{id}/start`
2. Play `song.fullMixUrl` once, then `POST /api/sessions/{id}/reference-complete`
3. Per player: upload recording to `POST /api/sessions/{id}/recordings`, then `POST /api/sessions/{id}/next-player` until `nextPhase` is `PROCESSING`
4. `POST /api/sessions/{id}/finalize` → play all anonymous performances → `POST /api/sessions/{id}/reveal-complete`
5. `POST /api/sessions/{id}/votes` (one per player) → `GET /api/sessions/{id}/results/final`

The exact request/response fields for each step are documented in [docs/INTEGRATION_CONTRACT.md](docs/INTEGRATION_CONTRACT.md); the OpenAPI schema at `/openapi.json` is the executable source of truth. `frontend/src/api/` types must be updated in the same commit as any change to the Pydantic models in `backend/app/models.py`.

### Audio pipeline (`backend/app/services/audio_service.py`)

Each uploaded recording goes through FFmpeg twice:
1. **Normalize**: trim/pad the raw upload to a 10-second mono 44.1kHz WAV, applying `applied_offset_ms` (clamped to [-2000, 5000]) to correct for the frontend's measured preroll.
2. **Mix**: combine the normalized vocal with the song's instrumental stem into `mix.mp3` (vocal boosted relative to the bed, limited to avoid clipping).

Silence is detected via RMS on the raw PCM samples (threshold 120), not via FFmpeg's silencedetect. `resolve_ffmpeg()` falls back from system `ffmpeg` → `FFMPEG_BIN` env var → the `imageio-ffmpeg`-bundled binary, so a working FFmpeg is available even on a machine with nothing pre-installed.

Media path separation is deliberate: raw uploads and normalized vocals live under `runtime/private/` (never served), while only `mix.mp3` files are exposed under `/media/sessions/` (mounted as static files in `backend/app/main.py`). Don't add a static mount that exposes `runtime/private/`.

### Scoring is currently a stub

`SessionService._score_for` only returns a `completion` score (100 if not silent, 0 if silent); pitch/rhythm/lyrics are always `None` with `confidence: "unavailable"` and `scoringProfile: "completion_only"`. `Feedback` is a hardcoded fallback string, not Gemini-generated. When implementing real scoring (per `backend/app/scoring/` in the intended layout) or Gemini/ElevenLabs integrations, preserve the contract that numeric scores are never influenced by AI feedback, and that every external call has a timeout with a local fallback (see the Fallback Matrix in the integration contract).

### Error handling

All non-2xx responses use one envelope:

```json
{"error": {"code": "SOME_CODE", "message": "...", "retryable": false, "details": {}}}
```

Raise `ApiError(status_code, code, message, retryable=..., details=...)` from `backend/app/errors.py` rather than raising bare `HTTPException` — the global handlers in `backend/app/main.py` normalize Starlette HTTP errors and Pydantic validation errors into this same shape, but domain errors (wrong phase, wrong player's turn, duplicate vote, self-vote, etc.) should use `ApiError` with a specific `code` so the frontend can branch on it without parsing message text.

### Song assets

`assets/songs/manifest.json` lists prepared songs; each song's folder needs `full.wav`, `instrumental.wav`, and `vocals.wav`. Stems are prepared offline with Demucs — Demucs is not part of the live request path, and there is no live source-separation code to maintain. `SongCatalog.is_ready()` checks file presence per song at request time, and `GET /api/songs` reports readiness so the frontend can disable Start for incomplete songs.

### Web Audio timing (frontend responsibility, not yet implemented)

The integration contract specifies a precise cross-clock timing handshake for recordings: capture `performance.now()` at `MediaRecorder` start, separately sample `performance.now()` beside `AudioContext.currentTime`, and derive `prerollMs` from those paired samples — never subtract `performance.now()` from `AudioContext.currentTime` directly (different clock origins), and never use `Date.now()` to schedule audio. The backend's `applied_offset_ms` clamping in `audio_service.py` assumes this contract is followed.
