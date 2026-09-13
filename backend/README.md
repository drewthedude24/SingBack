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
uvicorn backend.app.main:app --reload --port 8000
```

Then open <http://127.0.0.1:8000/docs> for the interactive API documentation.
The React development server at ports 5173 or 4173 is allowed by CORS.

## Test

```bash
pytest backend/tests
```

`imageio-ffmpeg` supplies a portable FFmpeg binary when `ffmpeg` is not already
installed. Set `FFMPEG_BIN` to an explicit binary if desired.

## Frontend integration order

Use this sequence for one complete round:

1. `GET /api/songs`
2. `POST /api/sessions`
3. `POST /api/sessions/{id}/start`
4. Play the returned `song.fullMixUrl` once.
5. `POST /api/sessions/{id}/reference-complete`
6. Upload the active player's multipart recording to
   `POST /api/sessions/{id}/recordings`.
7. Between players, call `POST /api/sessions/{id}/next-player`; repeat the
   upload until its `nextPhase` is `PROCESSING`.
8. `POST /api/sessions/{id}/finalize`, then play all anonymous performances.
9. Send all played IDs to `POST /api/sessions/{id}/reveal-complete`.
10. Submit one vote per player to `POST /api/sessions/{id}/votes`.
11. Read `GET /api/sessions/{id}/results/final`.

The OpenAPI schema at `/openapi.json` is the source for exact request and
response fields. All validation and game-state failures use the shared
`{"error": {"code", "message", "retryable", "details"}}` envelope.

Only generated `mix.mp3` files are exposed under `/media/sessions`. Raw uploads
and normalized vocals live under `runtime/private` and are not web-served.
