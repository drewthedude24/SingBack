import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { HostNarration } from "../components/HostNarration";
import { useGame } from "../game/GameProvider";
import { api } from "../api/client";
import type { AnalysisProgress } from "../api/types";

export function ProcessingScreen(): JSX.Element {
  const { session, retryProcessing, error, busy } = useGame();
  const startedRef = useRef(false);
  const [progress, setProgress] = useState(0);
  const [analysis, setAnalysis] = useState<AnalysisProgress | null>(null);

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
    if (!session) return;
    let cancelled = false;
    let timer = 0;
    const poll = async () => {
      try {
        const result = await api.analysisProgress(session.id);
        if (!cancelled) {
          setAnalysis(result);
          setProgress((current) => Math.max(current, result.percent));
        }
      } catch { /* The finalize request reports actionable errors. */ }
      if (!cancelled) timer = window.setTimeout(() => void poll(), 800);
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [session?.id]);

  const status = useMemo(() => {
    if (progress >= 100) return "Every performance is ready";
    if (analysis?.players.some((player) => player.stage === "audio")) return "Measuring pitch, rhythm, and completion";
    if (analysis?.players.some((player) => player.stage === "feedback")) return "Gemini is reviewing the performances";
    if (analysis?.players.some((player) => player.stage === "transcription")) return "Checking remembered lyrics with Scribe";
    return "Preparing the next performance for analysis";
  }, [progress, analysis]);

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
        aria-label="Completed analysis stages"
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
        {progress >= 100 ? "Analysis complete · opening the reveal" :
          `${analysis?.completedPlayers ?? 0} of ${analysis?.totalPlayers ?? session?.players.length ?? 1} performances ready · progress reflects completed stages`}
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
