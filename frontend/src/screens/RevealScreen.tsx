import { useState } from "react";

import { PerformanceCard } from "../components/PerformanceCard";
import { useGame } from "../game/GameProvider";

export function RevealScreen(): JSX.Element | null {
  const { revealResults, revealIndex, playedRevealIds, advanceReveal, finishReveal, busy } =
    useGame();
  const [gradedRevealIds, setGradedRevealIds] = useState<string[]>([]);

  if (!revealResults) return null;
  const total = revealResults.performances.length;
  const current = revealResults.performances[revealIndex];
  const isLast = revealIndex === total - 1;
  const gradingOpen = gradedRevealIds.includes(current.revealId);

  function openGrading(): void {
    setGradedRevealIds((ids) =>
      ids.includes(current.revealId) ? ids : [...ids, current.revealId],
    );
  }

  return (
    <section className="screen reveal-screen">
      <p className="eyebrow">
        Reveal &mdash; performance {revealIndex + 1} of {total}
      </p>
      <h1>Who could it be?</h1>

      <div className="reveal-progress">
        {revealResults.performances.map((performance, index) => (
          <span
            key={performance.revealId}
            className={`reveal-dot${index === revealIndex ? " reveal-dot-active" : ""}${
              playedRevealIds.includes(performance.revealId) ? " reveal-dot-played" : ""
            }`}
          />
        ))}
      </div>

      <div className="reveal-flip-wrap" key={current.revealId}>
        <PerformanceCard
          title={`Performance ${revealIndex + 1}`}
          mixUrl={current.mixUrl}
          score={gradingOpen ? current.score : undefined}
          feedback={gradingOpen ? current.feedback : undefined}
          detectedLyrics={gradingOpen ? current.detectedLyrics : undefined}
          evidence={gradingOpen ? current.evidence : undefined}
          onEnded={openGrading}
        />
      </div>

      {!gradingOpen ? (
        <div className="reveal-skip-row">
          <p className="reveal-instruction">Play the full performance, or reveal the grade immediately.</p>
          <button type="button" className="secondary-button" onClick={openGrading}>
            Show this grade now
          </button>
        </div>
      ) : null}

      <div className="reveal-actions">
        {!isLast ? (
          <button type="button" className="primary-button" onClick={advanceReveal}>
            Next performance
          </button>
        ) : (
          <button
            type="button"
            className="primary-button primary-button-large"
            disabled={busy}
            onClick={() => void finishReveal()}
          >
            Show final results
          </button>
        )}
        {!isLast ? (
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => void finishReveal()}
          >
            Skip all reveals &amp; see results
          </button>
        ) : null}
      </div>
    </section>
  );
}
