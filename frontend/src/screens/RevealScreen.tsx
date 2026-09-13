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
          onEnded={openGrading}
        />
      </div>

      {!gradingOpen ? (
        <p className="reveal-instruction">Play the full performance to unlock its grading.</p>
      ) : null}

      {!isLast ? (
        <button
          type="button"
          className="primary-button"
          disabled={!gradingOpen}
          onClick={advanceReveal}
        >
          Next performance
        </button>
      ) : (
        <button
          type="button"
          className="primary-button primary-button-large"
          disabled={busy || !gradingOpen}
          onClick={() => void finishReveal()}
        >
          Show final results
        </button>
      )}
    </section>
  );
}
