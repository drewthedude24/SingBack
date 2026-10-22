# Online rooms

Open https://singback.onrender.com and choose **Play online**. One person hosts;
friends join with the invitation link or six-character code. Each person enables
their own microphone and marks themselves ready. The host starts a mystery song.
Everyone listens on their device; then the server enforces one recording turn at
a time. Players see shared results automatically. Headphones prevent instrumental
bleed into microphone recordings.

## Backend contract

`POST /api/rooms` and `POST /api/rooms/{code}/join` take `{ "displayName": "…" }`
and return `{ code, token, room }`. Store the token on the joining device; never
include it in invitation links. Subsequent control requests use
`Authorization: Bearer <token>`. Poll `GET /api/rooms/{code}` approximately once
per second. It returns only that member's view, progress, and eventually results.

| Endpoint suffix | Method | Purpose |
| --- | --- | --- |
| `/ready` | POST | Set the current member's `{ "ready": true }` after mic permission |
| `/start` | POST | Host starts when 2–4 members are ready |
| `/listened` | POST | Acknowledge this member's reference playback |
| `/recordings` | POST | Multipart `file`, `mimeType`, `prerollMs`, `durationMs`; active member only |
| `/skip` | POST | Host advances missing listeners, or submits a silent take for the active player |
| `/retry` | POST | Host retries failed finalization without re-recording |
| `/rematch` | POST | Host returns everyone to the lobby after results |
| `/players/{playerId}` | DELETE | Host removes a lobby member |
| `/leave` | POST | Leave; a host ends the room |
| `/narration/{cue}` | GET | Optional ElevenLabs narration; listen/turn/processing/results |

All suffixes above are relative to `/api/rooms/{code}`. Internal pass-and-play
session IDs stay private; online result mix URLs are translated to room-scoped
URLs. The per-performance UUID is still needed to access a revealed mix. Raw
microphone recordings are never served by public media mounts.

The server assigns the song and turn order. Joining late, uploading another
player's turn, duplicate uploads, and guest host-control attempts are rejected.
An upload reservation prevents two requests from writing the same take at once.
FFmpeg runs outside the ASGI event loop, so uploads do not stop room polling.

## Progress and speed

Analysis starts immediately after every successful upload. An application-wide
executor bounds the queue to 32 jobs; a separate semaphore limits CPU-heavy
feature extraction (`MAX_ANALYSIS_WORKERS=1` in the free container). Scribe runs
concurrently with local feature extraction; remote Gemini feedback doesn't hold
the CPU slot. Finalization reuses these futures instead of analyzing takes again.

Progress reflects completed stages: started 5%, signal features 60%, transcript
20%, feedback 15%. The percentages are work-stage weights, **not elapsed-time
predictions**. Both online and pass-and-play expose this actual stage progress.

Immutable reference audio/pitch/onsets are generated for every song during the
Docker build. Cache keys include the file contents and scoring version. NumPy
loads cached data without pickle; invalid/missing data is recalculated. Player
pYIN now uses 20-cent bins rather than 10-cent bins. Score weights, octave
alignment, wrong-key penalties, and silence handling are retained; this is not
the old completion-only placeholder score.

## Deployment constraints

- Same origin HTTPS: phones do not need the host's LAN address or any API keys.
- One Uvicorn process; rooms and sessions currently use server memory.
- Tokens persist in **sessionStorage**, reconnecting the same tab after refresh.
  A separate browser or new device must join separately. No cross-device identity account.
- Rooms expire after six hours. Restarting/redeploying clears rooms and media.
- Presence is informational (20-second heartbeat grace); no automatic forfeits.
  The host must explicitly skip or end a stalled round.
- The free server can sleep; waking it is separate from grading performance.
- This demo is not designed for thousands of rooms or multi-instance deployment.
  That needs a shared state store, object storage, a durable job queue, request
  rate limiting, and stronger retention/abuse controls.

No `.env` changes or new provider keys are required. Existing Gemini and
ElevenLabs configuration is reused, and missing providers remain visibly labeled
as partial analysis/offline coaching rather than pretending that API calls ran.
