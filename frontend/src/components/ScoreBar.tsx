import { useEffect, useRef, useState } from "react";

const ANIMATION_MS = 700;

export function ScoreBar({
  label,
  value,
  confidence,
}: {
  label: string;
  value: number | null;
  confidence?: string;
}): JSX.Element {
  const target = value === null ? null : Math.max(0, Math.min(100, value));
  const [animated, setAnimated] = useState(0);
  const startRef = useRef<number | null>(null);

  useEffect(() => {
    if (target === null) return;
    startRef.current = null;
    let frameId = 0;
    const step = (timestamp: number) => {
      if (startRef.current === null) startRef.current = timestamp;
      const progress = Math.min(1, (timestamp - startRef.current) / ANIMATION_MS);
      setAnimated(target * progress);
      if (progress < 1) frameId = requestAnimationFrame(step);
    };
    frameId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frameId);
  }, [target]);
  return (
    <div className="score-bar">
      <div className="score-bar-label">
        <span>{label}</span>
        <span>{target === null ? "Unavailable" : Math.round(animated)}</span>
      </div>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{ width: target === null ? "0%" : `${animated}%` }}
        />
      </div>
      {confidence && confidence !== "ok" ? (
        <span className="score-bar-confidence">{confidence.replace(/_/g, " ")}</span>
      ) : null}
    </div>
  );
}
