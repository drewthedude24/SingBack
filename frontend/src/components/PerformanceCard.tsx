import { useRef } from "react";

import { mediaUrl } from "../api/client";
import type { Feedback, Score } from "../api/types";
import { MetricExplanations } from "./MetricExplanations";
import { ScoreBar } from "./ScoreBar";

interface PerformanceCardProps {
  title: string;
  mixUrl: string;
  score?: Score;
  feedback?: Feedback;
  detectedLyrics?: string | null;
  onEnded?: () => void;
  selectLabel?: string;
  onSelect?: () => void;
  disabled?: boolean;
}

export function PerformanceCard({
  title,
  mixUrl,
  score,
  feedback,
  detectedLyrics,
  onEnded,
  selectLabel,
  onSelect,
  disabled,
}: PerformanceCardProps): JSX.Element {
  const audioRef = useRef<HTMLAudioElement>(null);

  return (
    <div className="performance-card">
      <h3>{title}</h3>
      <audio
        ref={audioRef}
        controls
        src={mediaUrl(mixUrl)}
        onEnded={onEnded}
        className="performance-audio"
      />
      {score ? (
        <div className="performance-scores">
          <div className="analysis-meta">
            <span>{score.scoringProfile === "full" ? "Full analysis" : "Reduced analysis"}</span>
            {feedback ? (
              <span>{feedback.source === "gemini" ? "Gemini AI coach" : "Offline coach"}</span>
            ) : null}
          </div>
          <ScoreBar label="Pitch" value={score.pitch} confidence={score.confidence.pitch} />
          <ScoreBar label="Rhythm" value={score.rhythm} confidence={score.confidence.rhythm} />
          <ScoreBar label="Lyrics" value={score.lyrics} confidence={score.confidence.lyrics} />
          <ScoreBar
            label="Completion"
            value={score.completion}
            confidence={score.confidence.completion}
          />
          <div className="performance-total">Total: {Math.round(score.technicalTotal)}</div>
          <MetricExplanations />
        </div>
      ) : null}
      {feedback ? (
        <div className="performance-feedback">
          <p className="performance-feedback-summary">{feedback.summary}</p>
          <p>
            <strong>Strength:</strong> {feedback.strength}
          </p>
          <p>
            <strong>Try next:</strong> {feedback.improvement}
          </p>
          <p className="performance-announcer">"{feedback.announcerLine}"</p>
        </div>
      ) : null}
      {detectedLyrics ? (
        <p className="detected-lyrics">
          <strong>Heard:</strong> &ldquo;{detectedLyrics}&rdquo;
        </p>
      ) : null}
      {selectLabel && onSelect ? (
        <button type="button" className="primary-button" onClick={onSelect} disabled={disabled}>
          {selectLabel}
        </button>
      ) : null}
    </div>
  );
}
