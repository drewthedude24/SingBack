from __future__ import annotations

import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    repository_root = Path(__file__).resolve().parents[2]
    settings = Settings(
        repository_root=repository_root, runtime_root=tmp_path / "runtime"
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def vocal_wav() -> bytes:
    sample_rate = 44_100
    duration_seconds = 1.2
    frames = int(sample_rate * duration_seconds)
    output = io.BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        for index in range(frames):
            envelope = min(1.0, index / 2_000, (frames - index) / 2_000)
            sample = int(
                8_000 * envelope * math.sin(2 * math.pi * 220 * index / sample_rate)
            )
            wav_file.writeframesraw(struct.pack("<h", sample))
    return output.getvalue()
