import { useGame } from "../game/GameProvider";

export function HandoffScreen(): JSX.Element | null {
  const { nextPlayerForHandoff, lastRecording, continueAfterHandoff, busy } = useGame();

  return (
    <section className="screen handoff-screen">
      <p className="eyebrow">Take saved</p>
      <h1>Nice take!</h1>
      {lastRecording?.silent ? (
        <p className="field-error">
          That recording came through very quiet &mdash; move closer to the microphone next time.
        </p>
      ) : null}
      <p className="tagline">
        {nextPlayerForHandoff
          ? `Pass the device to ${nextPlayerForHandoff.displayName}.`
          : "Pass the device to the next player."}
      </p>
      <button
        type="button"
        className="primary-button primary-button-large"
        disabled={busy}
        onClick={() => void continueAfterHandoff()}
      >
        Continue
      </button>
    </section>
  );
}
