import { Countdown } from "../components/Countdown";
import { useGame } from "../game/GameProvider";

export function CountdownScreen(): JSX.Element {
  const { countdownValue, currentPlayer } = useGame();
  return (
    <section className="screen countdown-screen">
      <p className="eyebrow">Get ready, {currentPlayer?.displayName}</p>
      <Countdown value={countdownValue} />
    </section>
  );
}
