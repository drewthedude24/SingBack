# Public recruiter demo

SingBack deploys as one Docker web service. FastAPI serves the built React app,
API and audio from the same HTTPS origin, so visitors need no local installation
or API keys. The existing two-terminal development workflow also still works.

## Render

Deploy this repository's `main` branch using the root `Dockerfile`, or use the
[`render.yaml` Blueprint](../render.yaml). The service listens on Render's `PORT`
and uses `/api/health` as its health check. Run exactly one Uvicorn process because
game sessions live in process memory.

Set `GEMINI_API_KEY` and `ELEVENLABS_API_KEY` in Render's private environment
settings. Optional voice/model settings have the same names as local settings.
Never put provider keys in frontend variables or commit `.env`. Missing provider
keys enable the existing local fallbacks.

The free deployment uses `MAX_ANALYSIS_WORKERS=1` to bound memory consumption
across rounds. The local default remains four. The container prepares Numba's
disk cache for pitch, rhythm and DTW during its build, using portable CPU code
so the build cache also works on Render's runtime servers. It uses system
FFmpeg. Demucs is not needed at
runtime because all five song stems are included.

Free Render instances sleep after inactivity, so the first visit may show a
startup page for about a minute. Sessions and generated recordings are temporary
and reset when the service restarts or sleeps. This is a pass-and-play demo on
one device, not a synchronized room across multiple devices. Use HTTPS and allow
microphone access. Chrome or Edge on a laptop is the recommended demo setup.

## Verify a deployment

1. Open the root URL and confirm the game loads.
2. Visit `/api/health` and `/api/songs`; verify all songs are ready.
3. Create a solo game, hear the original clip, and record a take.
4. Verify the remix plays and waveform, scores, and coaching appear.
5. With provider keys configured, verify narration has audio and results report
   the actual feedback/transcription source rather than just key presence.

## Local production preview

```bash
cd frontend
npm ci
npm run build
cd ..
source .venv/bin/activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env
```

Open <http://127.0.0.1:8000>. If Docker is installed, the same packaged app runs
with `docker build -t singback .` followed by
`docker run --rm --env-file .env -p 8000:10000 singback`.

## Rollback

The exact remote code before deployment preparation is
`9db84ee81c723362ad51461803ae2acfb4cff558`, preserved by the Git tag
`pre-recruiter-deploy-20261022`. Revert the deployment commit(s) with `git revert`
and push to `main` to undo this work without overwriting other contributions.
Render automatically deploys changes to its tracked branch; reverting the code
does not itself delete the hosted service. Suspend the service in Render if the
deployment should be taken offline.
