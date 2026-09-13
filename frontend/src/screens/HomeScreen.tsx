import { useEffect, useState } from "react";

import { api } from "../api/client";
import { useGame } from "../game/GameProvider";

type BackendStatus = "checking" | "online" | "offline";

export function HomeScreen(): JSX.Element {
  const { micReady, micError, enableMicrophone, goToLobby, busy } = useGame();
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then(() => {
        if (!cancelled) setBackendStatus("online");
      })
      .catch(() => {
        if (!cancelled) setBackendStatus("offline");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="screen home-screen">
      <p className="eyebrow">HackRice Party Game</p>
      <h1>SingBack</h1>
      <div className="hero-visual" aria-hidden="true">
        <span className="hero-note">♪</span>
        <div className="hero-equalizer">
          {Array.from({ length: 18 }, (_, index) => (
            <span key={index} style={{ animationDelay: `${index * -70}ms` }} />
          ))}
        </div>
        <span className="hero-note hero-note-right">♫</span>
      </div>
      <p className="tagline">
        Everyone hears one short clip once. Then each player sings it back from memory over the
        same instrumental. Nobody hears a remix until every turn is done.
      </p>

      <ol className="rules-list">
        <li>Choose 1–4 players; SingBack draws a mystery song.</li>
        <li>Listen closely &mdash; the reference clip only plays once.</li>
        <li>Each player records their turn over the instrumental, one at a time.</li>
        <li>When everyone is done, every remix is revealed and scored.</li>
        <li>Reveal every performance, then crown the strongest technical score.</li>
      </ol>

      <div className="status-row">
        <span className={`status-dot status-${backendStatus}`} aria-hidden="true" />
        <span>
          {backendStatus === "checking" && "Checking backend connection..."}
          {backendStatus === "online" && "Connected to the SingBack backend."}
          {backendStatus === "offline" &&
            "Could not reach the backend. Start it with uvicorn backend.app.main:app --reload --port 8000."}
        </span>
      </div>

      <div className="mic-check">
        <button type="button" className="primary-button" onClick={() => void enableMicrophone()}>
          {micReady ? "Microphone ready" : "Enable microphone"}
        </button>
        {micError ? <p className="field-error">{micError}</p> : null}
      </div>

      <button
        type="button"
        className="primary-button primary-button-large"
        disabled={!micReady || busy}
        onClick={goToLobby}
      >
        Continue to Lobby
      </button>
    </section>
  );
}
