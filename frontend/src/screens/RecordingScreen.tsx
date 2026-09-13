import { useGame } from "../game/GameProvider";

export function RecordingScreen(): JSX.Element {
  const { currentPlayer, stopRecordingEarly } = useGame();
  return (
    <section className="screen recording-screen">
      <p className="eyebrow">Recording {currentPlayer?.displayName}</p>
      <div className="recording-indicator" aria-hidden="true" />
      <h1>Sing it back!</h1>
      <p className="tagline">The instrumental is playing. Recording stops automatically when it ends.</p>
      <button type="button" className="secondary-button" onClick={() => void stopRecordingEarly()}>
        Stop early
      </button>
    </section>
  );
}
