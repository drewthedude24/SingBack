import { useGame } from "../game/GameProvider";

export function TurnIntroScreen(): JSX.Element | null {
  const { session, currentPlayer, beginTurn } = useGame();
  if (!session || !currentPlayer) return null;

  return (
    <section className="screen turn-intro-screen">
      <p className="eyebrow">Turn {currentPlayer.turnOrder + 1} of {session.players.length}</p>
      <h1>Pass the device to {currentPlayer.displayName}</h1>
      <p className="tagline">
        When you are ready, you will get a three second countdown, then the instrumental will
        play while you sing the clip back from memory.
      </p>
      <button type="button" className="primary-button primary-button-large" onClick={() => void beginTurn()}>
        I&rsquo;m ready
      </button>
    </section>
  );
}
