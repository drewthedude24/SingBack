import { PerformanceCard } from "../components/PerformanceCard";
import { useGame } from "../game/GameProvider";

export function RevealScreen(): JSX.Element | null {
  const { revealResults, revealIndex, playedRevealIds, advanceReveal, continueToVoting, busy } =
    useGame();

  if (!revealResults) return null;
  const total = revealResults.performances.length;
  const current = revealResults.performances[revealIndex];
  const isLast = revealIndex === total - 1;

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

      <PerformanceCard
        title={`Performance ${revealIndex + 1}`}
        mixUrl={current.mixUrl}
        score={current.score}
        feedback={current.feedback}
      />

      {!isLast ? (
        <button type="button" className="primary-button" onClick={advanceReveal}>
          Next performance
        </button>
      ) : (
        <button
          type="button"
          className="primary-button primary-button-large"
          disabled={busy}
          onClick={() => void continueToVoting()}
        >
          Continue to voting
        </button>
      )}
    </section>
  );
}
