# SingBack Five Hour Sprint Plan

## Outcome

At the five-hour mark, three named players can complete one local pass-and-play round without a page reload. Each player gets a playable remix, the reveal stays hidden until all turns finish, scores are repeatable, voting works, and the app still completes the round if Gemini or ElevenLabs fails.

The sprint has one rule: protect the end-to-end game loop before improving any individual subsystem.

## Frozen MVP Scope

### Required

- One verified 10-second challenge with a full reference clip, instrumental stem, reference vocal stem, expected lyrics, and license/source record
- One laptop, one browser, three players, and local pass-and-play
- Lobby, listen-once, countdown, record, upload, processing, reveal, vote, and results states
- Browser microphone recording scheduled against the Web Audio clock
- FastAPI upload, FFmpeg conversion/alignment/mixing, SQLite persistence, and media serving
- Measured component scores with explicit confidence or unavailable states
- Gemini structured feedback when configured, with deterministic local feedback as fallback
- ElevenLabs host narration and Scribe lyric transcription when configured, with cached/text fallbacks
- Demo-safe prerecorded inputs for players two and three

### Deliberately Cut

- Online rooms, accounts, matchmaking, and cloud deployment
- Live Demucs separation; all stems must be prepared before the sprint
- Five production-ready songs; ship one verified song and leave manifest slots for the rest
- Presage, Voice Changer, Karaoke Mode, High Stakes Mode, and lyric hints
- WebSockets, background job infrastructure, and a production ORM migration system
- Perfect recovery after a browser refresh during an active recording
- Elaborate pitch graphs, animations, leaderboards, and mobile-first polish

If the required loop is not stable by hour four, Gemini feedback and live ElevenLabs calls become demo-cached fixtures rather than blockers.

## Team Ownership

### Teammate A Frontend and Game Flow

Owns `frontend/`.

- Create the React TypeScript Vite app and the screen shell.
- Put all game transitions in one reducer or state-machine module.
- Implement microphone permission, MediaRecorder capture, Web Audio scheduling, and timing metadata.
- Integrate the typed API client, playback, reveal gating, voting, results, and clear error/retry states.
- Never calculate authoritative scores or session rules in React.

### Teammate B Backend Database and External APIs

Owns `backend/app/api/`, `backend/app/db/`, `backend/app/integrations/`, and `.env.example`.

- Create FastAPI, CORS for local development, settings, health checks, and structured errors.
- Implement SQLite repositories for sessions, players, recordings, scores, and votes.
- Enforce state, turn order, safe filenames, MIME/size limits, reveal gating, and no self-voting.
- Add Gemini and ElevenLabs adapters behind interfaces with timeouts and deterministic fallbacks.
- Keep every secret on the backend.

### Teammate C Audio Scoring and Assets

Owns `backend/app/audio/`, `backend/app/scoring/`, `assets/`, and audio-focused tests.

- Prepare and manually verify the one legal 10-second song package before coding.
- Implement FFmpeg conversion to mono 44.1 kHz WAV, preroll trimming, conservative silence handling, normalization, and mixing.
- Implement the smallest real deterministic score: completion first, then pitch contour and rhythm if stable; lyric recall consumes the transcript from the integration boundary.
- Return component scores, confidence, and diagnostics. Silence and missing analysis must never produce NaN.
- Provide prerecorded demo vocals for players two and three and expected output fixtures.

### Integrator

The project owner acts as integrator. The integrator owns root configuration, the shared contract, dependency lockfiles, merges, smoke tests, and the final demo. If another teammate changes a shared contract, the integrator reviews and merges that change before dependents continue.

## Five Hour Clock

### 0:00 to 0:20 Contract and Setup

All three teammates:

- Confirm Node, Python, FFmpeg, microphones, API keys, and the prepared song files.
- Agree on the exact request/response shapes in `docs/INTEGRATION_CONTRACT.md`.
- Create short-lived branches: `feat/frontend`, `feat/backend`, and `feat/audio`.
- Pick one integrator. Only the integrator edits shared root files.

Checkpoint 0 passes when the song package is playable, the contract is frozen, and every teammate can run their toolchain.

### 0:20 to 1:00 Parallel Skeletons

- Frontend: lobby, reducer states, API client, microphone check, and mock session fixture.
- Backend: FastAPI app, health endpoint, SQLite initialization, session creation, media directory, and mock results fixture.
- Audio: FFmpeg command wrapper, song manifest validation, prerecorded vocal fixtures, and one conversion/mix test.

Checkpoint 1 passes when the frontend calls `/api/health`, creates a session, and renders the returned players/song. Commit and merge this thin integration before adding features.

### 1:00 to 2:00 One Player Vertical Slice

- Frontend records one player, starts capture roughly 500 ms before scheduled playback, records planned and observed start times, and uploads multipart form data.
- Backend validates and stores the upload, then calls the audio service.
- Audio service converts, aligns, and mixes the vocal with the instrumental.
- Backend returns a media URL; frontend plays the actual generated mix.

Checkpoint 2 passes only when a fresh browser recording travels through the real frontend, backend, filesystem, FFmpeg path, and back to a playable browser URL. Do not accept a mocked remix at this checkpoint.

### 2:00 to 3:10 Three Players Scoring and Reveal

- Extend the same upload path to all three players without duplicating components or endpoints.
- Persist session progress and artifacts in SQLite.
- Add silence detection and one retry.
- Calculate completion and stable pitch/rhythm components. Use an explicit unavailable result for any unfinished metric.
- Randomize reveal order on the backend and keep mixes hidden until every player is ready.
- Use prerecorded vocals for players two and three during repeated integration tests.

Checkpoint 3 passes when one live and two prepared recordings produce three mixes and three deterministic result objects, and the frontend cannot reveal them early.

### 3:10 to 4:00 Sponsor Integrations Voting and Results

- Backend sends each raw/converted vocal to ElevenLabs Scribe and maps word timestamps into lyric recall.
- Backend sends only measured metrics and transcript data to Gemini and validates structured output.
- Use cached host audio or text narration for fixed transitions; generate only the final winner line dynamically if reliable.
- Frontend plays every anonymized remix before enabling voting.
- Backend rejects self-votes and returns technical winner plus crowd favorite.

Checkpoint 4 passes with keys enabled and disabled. Both runs must reach results. Commit the integration adapters and their fallbacks together.

### 4:00 to 5:00 Freeze Test and Rehearse

- Stop feature work at 4:00 unless a required acceptance test is already green.
- Run the complete round at least three times: ideal path, denied/silent microphone path, and external API failure path.
- Check mix alignment with headphones and adjust one backend offset setting; do not add per-song timing logic.
- Rehearse a four-minute judge demo using one live performer and two prepared recordings.
- Freeze code at 4:35. Use the remaining time for bug fixes, README commands, screenshots/video, and submission text.

Checkpoint 5 passes when a teammate who did not build the frontend can launch the app from the README and complete the demo script.

## Integration Order

1. Health check and CORS
2. Session creation and song metadata
3. One real recording upload
4. One real FFmpeg-generated mix and media URL
5. Repeat for three players
6. Deterministic scores and reveal gating
7. Gemini and ElevenLabs adapters with fallbacks
8. Voting and results
9. Failure states and demo rehearsal

This order is intentional. Database completeness, scoring sophistication, and sponsor polish cannot precede the real recording-to-remix loop.

## Git Workflow and Checkpoints

- Use short-lived feature branches and merge at the five checkpoints above.
- Make small commits every 30 to 45 minutes with prefixes such as `feat:`, `fix:`, `test:`, and `docs:`.
- Never have two people edit the same root config, schema, reducer, or integration-contract file at the same time.
- Pull and rebase immediately before each checkpoint merge; the integrator runs the smoke test after every merge.
- A checkpoint commit must state what works end to end, not merely which files were added.
- Do not merge an endpoint change until the integration contract and frontend type are updated in the same checkpoint.

Recommended checkpoint commit subjects:

- `chore: establish SingBack sprint contracts`
- `feat: connect lobby to session API`
- `feat: complete recording to remix vertical slice`
- `feat: finish three player reveal and scoring`
- `feat: add resilient AI feedback and voting`
- `fix: harden and rehearse hackathon demo`

## Acceptance Test

The MVP is done when all of the following are true:

- A clean checkout starts with documented commands.
- Three names create one ordered local session.
- The reference clip can be played only once through the normal UI.
- Every turn records the microphone while the same instrumental is scheduled.
- Every upload stores timing metadata and creates a playable remix.
- The reveal is unavailable until all three artifacts are ready.
- Scores contain bounded numeric values or explicit unavailable states, never NaN.
- Gemini feedback cannot change numeric scores.
- The round completes without Gemini or ElevenLabs credentials.
- Voting starts only after every remix has played, and self-voting is rejected.
- Results name a technical winner and crowd favorite.

## Demo Script

1. Explain: Everyone hears a song once, then sings it back from memory.
2. Enter three player names and start the prepared challenge.
3. Play the reference once.
4. Record one live turn.
5. Use the prepared recordings for the other two turns.
6. Reveal all three remixes and the measured score breakdown.
7. Show Gemini feedback and play an ElevenLabs host line.
8. Cast the crowd vote and end on both winners.

## Immediate Preflight Questions

Answer these before the five-hour clock starts:

- Which teammate owns each of the three technical areas?
- Is the one licensed/team-produced clip already split and manually checked?
- Are FFmpeg, Python, and Node installed on the integrator laptop?
- Do the Gemini and ElevenLabs keys work from a backend-only test script?
- Which browser and laptop will be used for judging?
- Are wired headphones available for alignment testing?
