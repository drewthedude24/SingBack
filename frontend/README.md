# SingBack frontend

A React + TypeScript + Vite client for the SingBack MVP. It implements the full
game loop against the FastAPI backend described in
[`backend/README.md`](../backend/README.md) and
[`docs/INTEGRATION_CONTRACT.md`](../docs/INTEGRATION_CONTRACT.md): lobby, one-play
listen, per-player countdown/record/upload, reveal, voting, and results.

## Run locally

Start the backend first (from the repository root):

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Then, from `frontend/`:

```bash
npm install
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). The backend's CORS
config already allows `5173` and `4173`, so no proxy setup is needed.

By default the app talks to `http://127.0.0.1:8000`. To point at a different
backend, copy `.env.example` to `.env` and set `VITE_API_BASE_URL`.

## Type checking and build

```bash
npm run lint    # tsc --noEmit
npm run build   # tsc -b && vite build
npm run preview # serve the production build on port 4173
```

## How the pieces fit together

- `src/api/` &mdash; `types.ts` mirrors `backend/app/models.py` field-for-field
  (camelCase aliases); `client.ts` is a thin fetch wrapper that turns the
  backend's `{"error": {...}}` envelope into a typed `ApiRequestError`.
- `src/audio/` &mdash; `recorder.ts` wraps `MediaRecorder` and captures the exact
  `performance.now()` start timestamp the timing contract requires;
  `playback.ts` wraps a single `AudioContext` used to schedule the instrumental
  precisely rather than just calling `.play()`.
- `src/game/GameProvider.tsx` &mdash; the single state machine for the whole app.
  Backend phases (`LOBBY` &rarr; ... &rarr; `RESULTS`) come from `SessionView.phase`;
  local-only sub-stages (`countdown`, `recording`, `uploading`, the
  between-player `handoff` screen) exist only on the frontend, per the
  integration contract ("the frontend reducer may show local countdown and
  upload progress, but must not advance to reveal until the backend reports
  REVEAL").
- `src/screens/` &mdash; one component per stage, all reading from `useGame()`.

## Known limitations (matches current backend behavior)

- A session is always exactly three players &mdash; the backend's
  `CreateSessionRequest` requires `playerNames` of length 3.
- If a recording is detected as silent, the backend still accepts it and
  advances the turn (there is no reject-and-retry-before-storing endpoint yet).
  The UI surfaces a "that came through very quiet" note on the handoff screen
  but does not block progress.
- Reloading the page mid-session loses all local UI state (backend session
  state itself is in-memory only and does not survive a backend restart).
