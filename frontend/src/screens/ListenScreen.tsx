import { useRef, useState } from "react";

import { mediaUrl } from "../api/client";
import { useGame } from "../game/GameProvider";

export function ListenScreen(): JSX.Element | null {
  const { session, playReferenceEnded } = useGame();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [played, setPlayed] = useState(false);
  const [ended, setEnded] = useState(false);

  if (!session) return null;

  function handlePlay() {
    setPlayed(true);
    void audioRef.current?.play();
  }

  function handleEnded() {
    setEnded(true);
    void playReferenceEnded();
  }

  return (
    <section className="screen listen-screen">
      <p className="eyebrow">Listen closely</p>
      <h1>{session.song.title}</h1>
      <p className="tagline">You only get one play. Everyone should be listening now.</p>

      <audio ref={audioRef} src={mediaUrl(session.song.fullMixUrl)} onEnded={handleEnded} />

      {!played && (
        <button type="button" className="primary-button primary-button-large" onClick={handlePlay}>
          Play Reference Clip
        </button>
      )}
      {played && !ended && <p className="playing-indicator">Playing the reference clip...</p>}
      {ended && <p className="playing-indicator">Starting the first turn...</p>}
    </section>
  );
}
