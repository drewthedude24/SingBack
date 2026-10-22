"""Compare warm old/new pitch resolution on the same five public vocal clips.

Run: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m backend.scripts.benchmark_grading
No API calls, keys, or user recordings are used. This measures local DSP, not
Render wall time; deploy verification separately measures the live pipeline.
"""
import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

import librosa
import numpy as np
import soundfile as sf

from backend.app.config import Settings
from backend.app.scoring import service
from backend.app.services.song_catalog import SongCatalog


def main():
    settings = Settings()
    catalog = SongCatalog(settings.song_manifest_path, settings.repository_root)
    rows = []
    with tempfile.TemporaryDirectory(prefix="singback-benchmark-") as temporary:
        root = Path(temporary)
        for public in catalog.all_public():
            song = catalog.get(public.id)
            path = catalog.asset_path(song.reference_vocal_path)
            audio = service.ScoringService._load(path)
            shifted = root / f"{song.id}-wrong-key.wav"
            sf.write(shifted, librosa.effects.pitch_shift(audio, sr=service.SAMPLE_RATE, n_steps=2), service.SAMPLE_RATE)
            row = {"song": song.id}
            for label, resolution in [("before", .1), ("after", .2)]:
                service.PITCH_RESOLUTION = resolution
                scorer = service.ScoringService(cache_root=root / label / song.id)
                scorer.prepare_reference(path)
                def analyze(player_path):
                    return scorer.analyze(reference_vocal_path=path, player_vocal_path=player_path,
                        expected_lyrics=song.expected_lyrics, detected_lyrics=song.expected_lyrics,
                        transcript_source="elevenlabs")
                analyze(path)  # Exclude import/JIT from the warm benchmark.
                times = []
                for _ in range(3):
                    started = perf_counter()
                    same = analyze(path)
                    times.append(round((perf_counter() - started) * 1000, 2))
                wrong = analyze(shifted)
                assert same.score.technical_total >= 95
                assert wrong.score.pitch is not None and wrong.score.pitch < same.score.pitch - 5
                row[label] = {"samplesMs": times, "medianMs": statistics.median(times),
                    "identicalTotal": same.score.technical_total, "wrongKeyPitch": wrong.score.pitch,
                    "voicedSeconds": same.score.diagnostics["referenceVoicedSeconds"]}
            rows.append(row)
    before = statistics.median(row["before"]["medianMs"] for row in rows)
    after = statistics.median(row["after"]["medianMs"] for row in rows)
    print(json.dumps({"measurement": "warm local signal analysis; five clips; three timed runs each",
                      "beforeMedianMs": before, "afterMedianMs": after,
                      "reductionPercent": round((1 - after / before) * 100, 1),
                      "cases": rows}, indent=2))


if __name__ == "__main__":
    main()
