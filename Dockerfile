FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    MAX_ANALYSIS_WORKERS=1 \
    NUMBA_CACHE_DIR=/app/.cache/numba \
    MPLCONFIGDIR=/app/.cache/matplotlib \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1
WORKDIR /app
RUN apt-get update \
    && apt-get install --yes --no-install-recommends ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 singback
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --requirement backend/requirements.txt
COPY backend/ backend/
COPY assets/ assets/
COPY --from=frontend /build/frontend/dist/ frontend/dist/
RUN mkdir -p runtime .cache/numba .cache/matplotlib \
    && chown -R singback:singback runtime .cache
USER singback
# Populate Numba's disk cache during the build, before a recruiter's first game.
RUN python -c "from pathlib import Path; from backend.app.scoring.service import ScoringService; ScoringService().prepare_reference(Path('assets/songs/summer-day/vocals.wav'))"
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --timeout-keep-alive 30"]
