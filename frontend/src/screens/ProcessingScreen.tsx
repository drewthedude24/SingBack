import { useEffect, useMemo, useRef, useState } from "react";

import { HostNarration } from "../components/HostNarration";
import { useGame } from "../game/GameProvider";

export function ProcessingScreen(): JSX.Element {
  const { session, retryProcessing, error, busy } = useGame();
  const startedRef = useRef(false);
  const [progress, setProgress] = useState(6);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void retryProcessing();
  }, [retryProcessing]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setProgress((current) => {
        if (current >= 94) return current;
        if (current < 35) return Math.min(35, current + 3);
        if (current < 70) return Math.min(70, current + 1.5);
        return Math.min(94, current + 0.5);
      });
    }, 420);
    return () => window.clearInterval(timer);
  }, []);

  const status = useMemo(() => {
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
      <p className="processing-estimate">Estimated progress · external AI response time can vary</p>
      {session ? <HostNarration sessionId={session.id} cue="processing" /> : null}
      {error && !busy ? (
        <button type="button" className="primary-button" onClick={() => void retryProcessing()}>
          Try again
        </button>
      ) : null}
    </section>
  );
}
