import { useEffect, useMemo, useRef, useState } from "react";

import type { PerformanceEvidence } from "../api/types";
import { PerformanceEvidenceChart } from "./PerformanceEvidenceChart";

const BINS = 180;

function waveformBins(audio: Float32Array): number[] {
  if (audio.length === 0) return Array(BINS).fill(0) as number[];
  const values = Array.from({ length: BINS }, (_, index) => {
    const start = Math.floor((index / BINS) * audio.length);
    const end = Math.max(start + 1, Math.floor(((index + 1) / BINS) * audio.length));
    let energy = 0;
    for (let sampleIndex = start; sampleIndex < end; sampleIndex += 1) {
      energy += audio[sampleIndex] ** 2;
    }
    return Math.sqrt(energy / (end - start));
  });
  const peak = Math.max(...values, 0.000001);
  return values.map((value) => value / peak);
}

function normalized(values: number[]): number[] {
  const peak = Math.max(...values, 0.000001);
  return values.map((value) => value / peak);
}

export function LiveRecordingEvidence({
  referenceVocalUrl,
  analyser,
  currentMs,
  durationMs,
}: {
  referenceVocalUrl: string;
  analyser: AnalyserNode | null;
  currentMs: number;
  durationMs: number;
}): JSX.Element {
  const [referenceWaveform, setReferenceWaveform] = useState<number[]>(
    () => Array(BINS).fill(0) as number[],
  );
  const [playerWaveform, setPlayerWaveform] = useState<number[]>(
    () => Array(BINS).fill(0) as number[],
  );
  const currentMsRef = useRef(currentMs);
  const playerRawRef = useRef<number[]>(Array(BINS).fill(0) as number[]);
  const lastBinRef = useRef(0);

  currentMsRef.current = currentMs;

  useEffect(() => {
    let cancelled = false;
    const globalWindow = window as typeof window & { webkitAudioContext?: typeof AudioContext };
    const AudioContextCtor = globalWindow.AudioContext ?? globalWindow.webkitAudioContext;
    if (!AudioContextCtor) return;
    const context = new AudioContextCtor();
    void fetch(referenceVocalUrl)
      .then((response) => {
        if (!response.ok) throw new Error("Reference vocal could not be loaded.");
        return response.arrayBuffer();
      })
      .then((bytes) => context.decodeAudioData(bytes))
      .then((buffer) => {
        if (!cancelled) setReferenceWaveform(waveformBins(buffer.getChannelData(0)));
      })
      .catch(() => {
        if (!cancelled) setReferenceWaveform(Array(BINS).fill(0) as number[]);
      })
      .finally(() => void context.close());
    return () => {
      cancelled = true;
      void context.close();
    };
  }, [referenceVocalUrl]);

  useEffect(() => {
    if (!analyser || durationMs <= 0) return;
    const samples = new Float32Array(analyser.fftSize);
    let frameId = 0;
    let lastPaintMs = 0;
    const capture = (timestamp: number) => {
      analyser.getFloatTimeDomainData(samples);
      let energy = 0;
      for (const sample of samples) energy += sample * sample;
      const rms = Math.sqrt(energy / samples.length);
      const bin = Math.max(
        0,
        Math.min(BINS - 1, Math.floor((currentMsRef.current / durationMs) * BINS)),
      );
      for (let index = lastBinRef.current; index <= bin; index += 1) {
        playerRawRef.current[index] = Math.max(playerRawRef.current[index], rms);
      }
      lastBinRef.current = bin;
      if (timestamp - lastPaintMs >= 50) {
        lastPaintMs = timestamp;
        setPlayerWaveform(normalized([...playerRawRef.current]));
      }
      frameId = requestAnimationFrame(capture);
    };
    frameId = requestAnimationFrame(capture);
    return () => cancelAnimationFrame(frameId);
  }, [analyser, durationMs]);

  const evidence = useMemo<PerformanceEvidence>(
    () => ({
      durationMs: Math.max(1, durationMs),
      referenceWaveform,
      playerWaveform,
      referencePitchMidi: Array(BINS).fill(null) as null[],
      playerPitchMidi: Array(BINS).fill(null) as null[],
    }),
    [durationMs, playerWaveform, referenceWaveform],
  );

  return (
    <PerformanceEvidenceChart
      evidence={evidence}
      currentMs={currentMs}
      description="Live waveform capture · yellow line = current time"
      playerLabel="Your live vocal"
    />
  );
}
