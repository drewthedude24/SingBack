# SingBack Integration Contract

## Contract Rules

- The backend is authoritative for session phase, turn order, reveal readiness, and scores.
- The frontend owns presentation and transient countdown/recording progress, but it requests every legal phase change through the API.
- Audio and external APIs are services behind backend interfaces; routes do not contain FFmpeg, Librosa, Gemini, or ElevenLabs implementation details.
- All timestamps in JSON use ISO 8601 UTC. All audio offsets and durations use integer milliseconds.
- All score fields are either numbers from 0 through 100 or `null` with a confidence/status explanation.
- Every external integration has a timeout and a local fallback.

## Minimal Repository Boundaries

```text
SingBack/
  frontend/
    src/api/
    src/audio/
    src/game/
    src/screens/
  backend/
    app/api/
    app/audio/
    app/db/
    app/integrations/
    app/scoring/
    tests/
  assets/songs/
  docs/
  scripts/
```

`frontend/src/api/` mirrors the request and response shapes below. The backend Pydantic models are the source of truth. During this sprint, update the TypeScript types in the same commit as any Pydantic contract change.

## Game Phases

```text
LOBBY -> LISTEN -> TURN_INTRO -> COUNTDOWN -> RECORDING -> UPLOADING
UPLOADING -> NEXT_PLAYER -> TURN_INTRO
UPLOADING -> PROCESSING -> REVEAL -> RESULTS
any active phase -> ERROR -> last recoverable phase
```

The frontend reducer may show local countdown and upload progress, but it must not advance to reveal until the backend reports `REVEAL` and all artifacts are ready.

## Song Manifest

```json
{
  "id": "demo_song",
  "title": "Demo Song",
  "artist": "Team SingBack",
  "licenseName": "Team produced",
  "sourceUrl": "https://example.com/license-record",
  "durationMs": 10000,
  "fullMixUrl": "/media/songs/demo_song/full.wav",
  "instrumentalPath": "assets/songs/demo_song/instrumental.wav",
  "referenceVocalPath": "assets/songs/demo_song/vocals.wav",
  "expectedLyrics": "expected lyric phrase",
  "bpm": null,
  "key": null
}
```

Browser clients receive media URLs, never server filesystem paths.

## API Surface

### `GET /api/health`

```json
{
  "status": "ok",
  "ffmpeg": true,
  "gemini": "configured",
  "elevenlabs": "configured"
}
```

External services being unconfigured must not make health return a non-200 response.

### `GET /api/songs`

Returns public metadata and readiness for prepared songs. The frontend disables Start if no song is ready.

### `POST /api/sessions`

Request:

```json
{
  "playerNames": ["Ava", "Ben", "Cam"],
  "songId": "demo_song"
}
```

Response:

```json
{
  "id": "session_uuid",
  "phase": "LOBBY",
  "song": {
    "id": "demo_song",
    "title": "Demo Song",
    "durationMs": 10000,
    "fullMixUrl": "/media/songs/demo_song/full.wav",
    "instrumentalUrl": "/media/songs/demo_song/instrumental.wav",
    "expectedLyrics": "expected lyric phrase"
  },
  "players": [
    {"id": "player_uuid", "displayName": "Ava", "turnOrder": 0}
  ],
  "currentPlayerId": "player_uuid",
  "allArtifactsReady": false
}
```

### `POST /api/sessions/{sessionId}/start`

Valid only from `LOBBY`. Returns the complete session view with phase `LISTEN`.

### `GET /api/sessions/{sessionId}/narration/{cue}`

Valid cues are `listen`, `turn`, `processing`, and `results`. Returns the host
line as text in every case and an ElevenLabs-generated `audioUrl` when TTS is
configured and succeeds. The results cue is valid only after reveal completes.

### `POST /api/sessions/{sessionId}/reference-complete`

Valid only from `LISTEN`. Records that the one-play reference ended and returns `TURN_INTRO` for player one. Repeated calls return a conflict.

### `POST /api/sessions/{sessionId}/recordings`

Send `multipart/form-data` with:

- `file`: browser audio blob
- `playerId`: UUID
- `mimeType`: actual `MediaRecorder.mimeType`
- `recordingStartPerfMs`: `performance.now()` captured from the recorder start event
- `clockSamplePerfMs`: `performance.now()` sampled immediately beside the Web Audio clock
- `clockSampleAudioSec`: `AudioContext.currentTime` from the same clock sample
- `plannedPlaybackAudioSec`: scheduled Web Audio start time
- `prerollMs`: derived planned playback time minus recorder start time
- `durationMs`: recorded duration
- `isDemoFixture`: boolean, allowed only in development/demo mode

Successful response:

```json
{
  "recordingId": "recording_uuid",
  "status": "ready",
  "rawUrl": null,
  "mixUrl": "/media/sessions/session_uuid/player_uuid/mix.mp3",
  "detectedDurationMs": 10512,
  "appliedOffsetMs": 487,
  "silent": false,
  "nextPhase": "NEXT_PLAYER"
}
```

Raw vocal media is never exposed to another player before results and should normally remain private even afterward.

### `POST /api/sessions/{sessionId}/next-player`

Valid only from `NEXT_PLAYER`. Advances to `TURN_INTRO`, updates
`currentPlayerId`, and returns the complete session view. The frontend calls
this after its between-player handoff screen; it must not increment turn order
locally.

### `POST /api/sessions/{sessionId}/finalize`

Valid only when all recordings are ready. For the five-hour build this can be a synchronous request with a clear frontend timeout and one retry. It calculates or loads scores, requests optional AI feedback/narration, freezes reveal order, and returns phase `REVEAL`.

### `GET /api/sessions/{sessionId}`

Returns the full resumable session view. Before `REVEAL`, it must not return another player's `mixUrl`, score, transcript, feedback, or reveal identity.

### `GET /api/sessions/{sessionId}/results`

Before reveal, return `409`. During reveal, return anonymous entries in frozen random order:

```json
{
  "sessionId": "session_uuid",
  "phase": "REVEAL",
  "performances": [
    {
      "revealId": "reveal_1",
      "mixUrl": "/media/sessions/session_uuid/player_uuid/mix.mp3",
      "score": {
        "pitch": 81.2,
        "rhythm": 74.0,
        "lyrics": 90.0,
        "completion": 100.0,
        "technicalTotal": 83.04,
        "scoringProfile": "full",
        "confidence": {"pitch": "ok", "rhythm": "ok", "lyrics": "ok"},
        "diagnostics": {"pitchMeanErrorSemitones": 1.25, "transcriptSource": "elevenlabs"}
      },
      "feedback": {
        "summary": "Strong melody recall with one late entrance.",
        "strength": "The final phrase stayed close to the reference.",
        "improvement": "Start the second line slightly earlier.",
        "announcerLine": "The melody survived the memory test.",
        "tags": ["accurate melody", "late entrance"],
        "source": "gemini"
      },
      "detectedLyrics": "expected lyric phrase"
    }
  ]
}
```

`feedback.source` is `gemini` or `fallback`. Numeric scores never come from Gemini.

The full score uses the PRD weights: 45% pitch, 25% rhythm, 20% lyrics, and 10% completion. If transcription is unavailable, set `lyrics` to `null`, reweight only the three measured components to 100%, and return `scoringProfile: "partial_no_lyrics"`. The UI must label that result as reduced-confidence instead of presenting it as equivalent to a full score.

### `POST /api/sessions/{sessionId}/reveal-complete`

Marks every reveal entry acknowledged (played or deliberately skipped) and advances
directly to `RESULTS`. The backend rejects the call unless every reveal ID is sent
exactly once.

### `GET /api/sessions/{sessionId}/results/final`

Returns identities, metric details, the technical winner, and optional host narration URL after reveal is complete.

## Error Shape

Every non-2xx response uses:

```json
{
  "error": {
    "code": "INVALID_SESSION_PHASE",
    "message": "Recordings are accepted only during the active player's turn.",
    "retryable": false,
    "details": {}
  }
}
```

The UI branches on `code`, not on human-readable text.

## Service Interfaces

```text
AudioService.convert_and_mix(recording, song, timing) -> AudioArtifact
ScoringService.score(raw_wav, reference_vocal, transcript) -> ScoreResult
TranscriptionService.transcribe(raw_wav, expected_lyrics) -> TranscriptResult
FeedbackService.generate(score, transcript, expected_lyrics) -> FeedbackResult
NarrationService.synthesize(text, cache_key) -> NarrationResult
```

Each result includes `status`, `durationMs`, and an error code when unavailable. Routes call interfaces; tests replace them with fixtures.

## SQLite Minimum

- `sessions`: id, phase, song_id, current_player_index, reveal_order_json, created_at
- `players`: id, session_id, display_name, turn_order
- `recordings`: id, player_id, raw_path, wav_path, mix_path, offset_ms, duration_ms, status
- `scores`: player_id, pitch, rhythm, lyrics, completion, technical_total, confidence_json, feedback_json
Use database constraints for unique turn order per session. Use generated UUID filenames and resolve every media path under a configured media root before serving it.

## Audio Timing Contract

1. Request the microphone before the turn.
2. Start `MediaRecorder`, wait for its start event, and capture `performance.now()`.
3. Sample `performance.now()` beside `AudioContext.currentTime`, then schedule a decoded `AudioBufferSourceNode` about 500 ms in the future.
4. Derive and send `prerollMs` plus both raw clock samples and the actual MIME type for debugging.
5. Convert to mono 44.1 kHz PCM WAV.
6. Trim the measured preroll plus one configurable calibration offset.
7. Reject or retry near-silent recordings.
8. Mix without stretching the performance.

Do not subtract a `performance.now()` value directly from `AudioContext.currentTime`; they have different clock origins. Do not use `Date.now()` to schedule audio. The frontend derives the cross-clock preroll from a paired sample and the backend applies that duration plus its calibration offset.

## Fallback Matrix

| Failure | User-visible behavior | Stored status |
| --- | --- | --- |
| Microphone denied | Explain how to allow access and offer retry | No recording created |
| Silent recording | Offer one immediate retry | `rejected_silent` |
| FFmpeg failure | Keep player on upload/error state | `processing_failed` |
| Scribe unavailable | Mark lyric score unavailable or use a declared demo fixture | `transcription_unavailable` |
| Gemini unavailable | Generate feedback from score thresholds | Feedback source `fallback` |
| ElevenLabs TTS unavailable | Show text and play cached line if present | Narration source `text` or `cache` |

## Current Documentation References

- [MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- [Web Audio currentTime](https://developer.mozilla.org/en-US/docs/Web/API/BaseAudioContext/currentTime)
- [FastAPI file uploads](https://fastapi.tiangolo.com/tutorial/request-files/)
- [FastAPI static files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [ElevenLabs speech to text](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
