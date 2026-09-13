import { PerformanceCard } from "../components/PerformanceCard";
import { useGame } from "../game/GameProvider";

export function ResultsScreen(): JSX.Element | null {
  const { finalResults, playAgain } = useGame();
  if (!finalResults) return null;

  const technicalWinner = finalResults.performances.find(
    (performance) => performance.playerId === finalResults.technicalWinnerPlayerId,
  );
  const crowdFavorite = finalResults.performances.find(
    (performance) => performance.playerId === finalResults.crowdFavoritePlayerId,
  );

  return (
    <section className="screen results-screen">
      <p className="eyebrow">Results</p>
      <h1>Round complete!</h1>

      <div className="award-row">
        <div className="award-card">
          <p className="award-label">Technical winner</p>
          <p className="award-name">{technicalWinner?.displayName ?? "-"}</p>
        </div>
        <div className="award-card">
          <p className="award-label">Crowd favorite</p>
          <p className="award-name">{crowdFavorite?.displayName ?? "-"}</p>
        </div>
      </div>

      <div className="performance-grid">
        {finalResults.performances.map((performance) => (
          <PerformanceCard
            key={performance.revealId}
            title={`${performance.displayName} — ${performance.votes} vote${
              performance.votes === 1 ? "" : "s"
            }`}
            mixUrl={performance.mixUrl}
            score={performance.score}
            feedback={performance.feedback}
          />
        ))}
      </div>

      <button type="button" className="primary-button primary-button-large" onClick={playAgain}>
        Play again
      </button>
    </section>
  );
}
