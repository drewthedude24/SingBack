import { useMemo } from "react";

import type { PerformanceEvidence } from "../api/types";

const WIDTH = 1000;
const HEIGHT = 300;
const PLOT_LEFT = 28;
const PLOT_RIGHT = 972;
const TRACK_HEIGHT = 82;
const REFERENCE_CENTER = 88;
const PLAYER_CENTER = 220;

function waveformPath(values: number[], center: number): string {
  if (values.length === 0) return "";
  const xFor = (index: number) =>
    PLOT_LEFT + (index / Math.max(1, values.length - 1)) * (PLOT_RIGHT - PLOT_LEFT);
  const upper = values.map(
    (value, index) => `${xFor(index)},${center - value * TRACK_HEIGHT * 0.46}`,
  );
  const lower = values
    .map((value, index) => `${xFor(index)},${center + value * TRACK_HEIGHT * 0.46}`)
    .reverse();
  return `M ${upper.join(" L ")} L ${lower.join(" L ")} Z`;
}

function pitchPaths(
  values: Array<number | null>,
  center: number,
  minimum: number,
  maximum: number,
): string[] {
  const paths: string[] = [];
  let current = "";
  values.forEach((value, index) => {
    if (value === null) {
      if (current) paths.push(current);
      current = "";
      return;
    }
    const x = PLOT_LEFT + (index / Math.max(1, values.length - 1)) * (PLOT_RIGHT - PLOT_LEFT);
    const normalized = (value - minimum) / Math.max(1, maximum - minimum);
    const y = center + TRACK_HEIGHT * 0.42 - normalized * TRACK_HEIGHT * 0.84;
    current += `${current ? " L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  if (current) paths.push(current);
  return paths;
}

function formatTime(milliseconds: number): string {
  return `${(milliseconds / 1000).toFixed(1)}s`;
}

export function PerformanceEvidenceChart({
  evidence,
  currentMs,
}: {
  evidence: PerformanceEvidence;
  currentMs: number;
}): JSX.Element {
  const pitchRange = useMemo(() => {
    const values = [...evidence.referencePitchMidi, ...evidence.playerPitchMidi].filter(
      (value): value is number => value !== null,
    );
    if (values.length === 0) return { minimum: 48, maximum: 72 };
    return {
      minimum: Math.floor(Math.min(...values) - 2),
      maximum: Math.ceil(Math.max(...values) + 2),
    };
  }, [evidence]);

  const progress = Math.max(0, Math.min(1, currentMs / evidence.durationMs));
  const playheadX = PLOT_LEFT + progress * (PLOT_RIGHT - PLOT_LEFT);
  const referencePitchPaths = pitchPaths(
    evidence.referencePitchMidi,
    REFERENCE_CENTER,
    pitchRange.minimum,
    pitchRange.maximum,
  );
  const playerPitchPaths = pitchPaths(
    evidence.playerPitchMidi,
    PLAYER_CENTER,
    pitchRange.minimum,
    pitchRange.maximum,
  );

  return (
    <figure className="performance-evidence">
      <figcaption>
        <strong>What the grader heard</strong>
        <span>Waveform = loudness · line = detected pitch (octave-aligned)</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label="Reference and player vocal waveforms with pitch traces and synchronized playhead"
      >
        <rect x="0" y="35" width={WIDTH} height="106" rx="18" className="evidence-track-bg" />
        <rect x="0" y="167" width={WIDTH} height="106" rx="18" className="evidence-track-bg" />
        <text x="20" y="27" className="evidence-label evidence-reference-label">Original vocal</text>
        <text x="20" y="159" className="evidence-label evidence-player-label">Your vocal</text>
        <path d={waveformPath(evidence.referenceWaveform, REFERENCE_CENTER)} className="evidence-waveform-reference" />
        <path d={waveformPath(evidence.playerWaveform, PLAYER_CENTER)} className="evidence-waveform-player" />
        {referencePitchPaths.map((path, index) => (
          <path key={`reference-${index}`} d={path} className="evidence-pitch-reference" />
        ))}
        {playerPitchPaths.map((path, index) => (
          <path key={`player-${index}`} d={path} className="evidence-pitch-player" />
        ))}
        <line x1={playheadX} x2={playheadX} y1="30" y2="278" className="evidence-playhead" />
        <rect x={Math.min(910, Math.max(4, playheadX - 42))} y="278" width="84" height="22" rx="8" className="evidence-time-bg" />
        <text x={Math.min(952, Math.max(46, playheadX))} y="294" textAnchor="middle" className="evidence-time">
          {formatTime(progress * evidence.durationMs)}
        </text>
      </svg>
    </figure>
  );
}
