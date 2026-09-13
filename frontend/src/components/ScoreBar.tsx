export function ScoreBar({
  label,
  value,
  confidence,
}: {
  label: string;
  value: number | null;
  confidence?: string;
}): JSX.Element {
  const displayValue = value === null ? null : Math.max(0, Math.min(100, value));
  return (
    <div className="score-bar">
      <div className="score-bar-label">
        <span>{label}</span>
        <span>{displayValue === null ? "Unavailable" : Math.round(displayValue)}</span>
      </div>
      <div className="score-bar-track">
        <div
          className="score-bar-fill"
          style={{ width: displayValue === null ? "0%" : `${displayValue}%` }}
        />
      </div>
      {confidence && confidence !== "ok" ? (
        <span className="score-bar-confidence">{confidence.replace(/_/g, " ")}</span>
      ) : null}
    </div>
  );
}
