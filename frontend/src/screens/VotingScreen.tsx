import { PerformanceCard } from "../components/PerformanceCard";
import { useGame } from "../game/GameProvider";

export function VotingScreen(): JSX.Element | null {
  const { revealResults, voter, voteMessage, castVote, busy } = useGame();
  if (!revealResults || !voter) return null;

  return (
    <section className="screen voting-screen">
      <p className="eyebrow">Voting</p>
      <h1>Pass the device to {voter.displayName}</h1>
      <p className="tagline">
        Listen again if you like, then choose your favorite performance. You cannot vote for
        yourself.
      </p>

      {voteMessage ? <p className="field-error">{voteMessage}</p> : null}

      <div className="performance-grid">
        {revealResults.performances.map((performance, index) => (
          <PerformanceCard
            key={performance.revealId}
            title={`Performance ${index + 1}`}
            mixUrl={performance.mixUrl}
            selectLabel="Vote for this one"
            disabled={busy}
            onSelect={() => void castVote(performance.revealId)}
          />
        ))}
      </div>
    </section>
  );
}
