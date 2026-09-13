const METRICS = [
  ["Pitch", "How closely your melody followed the reference, allowing a different vocal octave."],
  ["Rhythm", "How closely your entrances and phrase spacing matched the reference."],
  ["Lyrics", "How many expected words ElevenLabs Scribe detected in your take."],
  ["Completion", "How much of the reference vocal duration you completed."],
] as const;

export function MetricExplanations(): JSX.Element {
  return (
    <details className="metric-explanations">
      <summary>How was this graded?</summary>
      <dl>
        {METRICS.map(([label, description]) => (
          <div key={label} className="metric-explanation-row">
            <dt>{label}</dt>
            <dd>{description}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
