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
    NUMBA_CPU_NAME=generic \
    NUMBA_CACHE_DIR=/app/.cache/numba \
    REFERENCE_CACHE_DIR=/app/.cache/references \
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
# Compile pitch, onset and DTW kernels during the build. Generic CPU code keeps
# this cache reusable when Render builds and runs on different x86 processors.
RUN python -m backend.scripts.prepare_reference_features
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --timeout-keep-alive 30"]
