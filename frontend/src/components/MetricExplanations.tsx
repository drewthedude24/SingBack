import type { Score } from "../api/types";

function diagnostic(score: Score, key: string): string | number | null {
  return score.diagnostics[key] ?? null;
}

export function MetricExplanations({ score }: { score: Score }): JSX.Element {
  const pitchError = diagnostic(score, "pitchMeanErrorSemitones");
  const rhythmError = diagnostic(score, "rhythmMeanErrorMs");
  const lyricError = diagnostic(score, "lyricWordErrorRate");
  const referenceVoiced = diagnostic(score, "referenceVoicedSeconds");
  const playerVoiced = diagnostic(score, "playerVoicedSeconds");
  const transcriptSource = diagnostic(score, "transcriptSource");
  const transcriptionMs = diagnostic(score, "transcriptionMs");
  const localAnalysisMs = diagnostic(score, "localAnalysisMs");
  const geminiFeedbackMs = diagnostic(score, "geminiFeedbackMs");

  return (
    <details className="metric-explanations">
      <summary>How was this graded?</summary>
      <p className="grading-formula">
        The numeric grade is measured—not guessed by Gemini: 45% pitch + 25% rhythm +
        20% lyrics + 10% completion. If a measurement is unavailable, the remaining
        weights are proportionally rebalanced.
      </p>
      <dl>
        <div className="metric-explanation-row">
          <dt>Pitch · 45%</dt>
          <dd>
            Librosa traces both melodies, aligns their timing, allows an octave for vocal
            range, then deducts 10 points per average semitone of error.
            {typeof pitchError === "number"
              ? ` This take averaged ${pitchError} semitones.`
              : " No stable player pitch was detected."}
          </dd>
        </div>
        <div className="metric-explanation-row">
          <dt>Rhythm · 25%</dt>
          <dd>
            Compares the spacing between detected note/phrase entrances, with a penalty for
            missing or extra entrances—not the device's constant start latency. The formula is
            100 × e^(−mean error ÷ 0.4 seconds) × entrance coverage.
            {typeof rhythmError === "number" ? ` Mean timing error: ${Math.round(rhythmError)} ms.` : ""}
          </dd>
        </div>
        <div className="metric-explanation-row">
          <dt>Lyrics · 20%</dt>
          <dd>
            ElevenLabs Scribe transcribes the vocal, then word-level edit distance compares it
            with the expected phrase: max(0, 100 × (1 − word error rate)).
            {typeof lyricError === "number" ? ` Word error rate: ${Math.round(lyricError * 100)}%.` : " Transcription was unavailable."}
          </dd>
        </div>
        <div className="metric-explanation-row">
          <dt>Completion · 10%</dt>
          <dd>
            Compares voiced singing duration in both clips and penalizes takes that are too
            short or excessively long: 100 × shorter voiced duration ÷ longer voiced duration.
            {typeof referenceVoiced === "number" && typeof playerVoiced === "number"
              ? ` Reference: ${referenceVoiced}s; player: ${playerVoiced}s.`
              : ""}
          </dd>
        </div>
      </dl>
      <p className="grading-ai-note">
        Gemini hears both isolated vocals and turns these fixed measurements into coaching;
        it cannot change the score. Transcript source: {String(transcriptSource ?? "unavailable")}.
      </p>
      <p className="grading-timing">
        Processing for this take: local analysis {typeof localAnalysisMs === "number" ? `${(localAnalysisMs / 1000).toFixed(1)}s` : "—"},
        transcription {typeof transcriptionMs === "number" ? `${(transcriptionMs / 1000).toFixed(1)}s` : "—"},
        Gemini {typeof geminiFeedbackMs === "number" ? `${(geminiFeedbackMs / 1000).toFixed(1)}s` : "—"}.
      </p>
    </details>
  );
}
