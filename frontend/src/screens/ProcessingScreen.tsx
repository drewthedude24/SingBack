import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { HostNarration } from "../components/HostNarration";
import { useGame } from "../game/GameProvider";

export function ProcessingScreen(): JSX.Element {
  const { session, retryProcessing, error, busy } = useGame();
  const startedRef = useRef(false);
  const [progress, setProgress] = useState(6);

  const finishProgress = useCallback(async () => {
    setProgress(100);
    await new Promise<void>((resolve) => window.setTimeout(resolve, 450));
  }, []);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void retryProcessing(finishProgress);
  }, [finishProgress, retryProcessing]);

  useEffect(() => {
    const startedAt = performance.now();
    const timer = window.setInterval(() => {
      const elapsedMs = performance.now() - startedAt;
      let estimated: number;
      if (elapsedMs < 700) {
        estimated = 6 + (elapsedMs / 700) * 34;
      } else if (elapsedMs < 2_200) {
        estimated = 40 + ((elapsedMs - 700) / 1_500) * 25;
      } else if (elapsedMs < 5_000) {
        estimated = 65 + ((elapsedMs - 2_200) / 2_800) * 20;
      } else {
        estimated = Math.min(96, 85 + ((elapsedMs - 5_000) / 8_000) * 11);
      }
      setProgress((current) => (current >= 100 ? current : Math.max(current, estimated)));
    }, 100);
    return () => window.clearInterval(timer);
  }, []);

  const status = useMemo(() => {
    if (progress >= 100) return "Every performance is ready";
    if (progress < 30) return "Preparing and aligning each vocal";
    if (progress < 58) return "Tracing pitch, rhythm, and completion";
    if (progress < 78) return "Checking remembered lyrics";
    return "Asking the AI coach for grounded feedback";
  }, [progress]);

  return (
    <section className="screen processing-screen">
      <div className="processing-stage" aria-hidden="true">
        <div className="processing-record processing-record-back" />
        <div className="processing-record processing-record-front">
          <span>SB</span>
        </div>
        <span className="processing-note processing-note-one">♪</span>
        <span className="processing-note processing-note-two">♫</span>
      </div>
      <p className="eyebrow">Loading performances</p>
      <h1>Building the big reveal</h1>
      <p className="processing-status">{status}</p>
      <div
        className="processing-progress"
        role="progressbar"
        aria-label="Estimated processing progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress)}
      >
        <div className="processing-progress-track">
          <div className="processing-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <strong>{Math.round(progress)}%</strong>
      </div>
      <p className="processing-estimate">
        {progress >= 100 ? "Analysis complete · opening the reveal" : "Estimated progress · external AI response time can vary"}
      </p>
      {session ? <HostNarration sessionId={session.id} cue="processing" /> : null}
      {error && !busy ? (
        <button
          type="button"
          className="primary-button"
          onClick={() => void retryProcessing(finishProgress)}
        >
          Try again
        </button>
      ) : null}
    </section>
  );
}
