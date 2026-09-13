import { PerformanceCard } from "../components/PerformanceCard";
import { HostNarration } from "../components/HostNarration";
import { useGame } from "../game/GameProvider";

export function ResultsScreen(): JSX.Element | null {
  const { session, finalResults, playAgain } = useGame();
  if (!session || !finalResults) return null;

  const technicalWinner = finalResults.performances.find(
    (performance) => performance.playerId === finalResults.technicalWinnerPlayerId,
  );
  return (
    <section className="screen results-screen">
      <p className="eyebrow">Results</p>
      <h1>Round complete!</h1>
      <HostNarration sessionId={session.id} cue="results" />

      <div className="award-row">
        <div className="award-card">
          <p className="award-label">Technical winner</p>
          <p className="award-name">{technicalWinner?.displayName ?? "-"}</p>
        </div>
      </div>

      <div className="performance-grid">
        {finalResults.performances.map((performance) => (
          <PerformanceCard
            key={performance.revealId}
            title={performance.displayName}
            mixUrl={performance.mixUrl}
            score={performance.score}
            feedback={performance.feedback}
            detectedLyrics={performance.detectedLyrics}
          />
        ))}
      </div>

      <button type="button" className="primary-button primary-button-large" onClick={playAgain}>
        Play again
      </button>
    </section>
  );
}
