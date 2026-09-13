import { useEffect, useRef, useState } from "react";

import { mediaUrl } from "../api/client";
import { HostNarration } from "../components/HostNarration";
import { LyricDisplay } from "../components/LyricDisplay";
import { LyricsPrompt } from "../components/LyricsPrompt";
import { useGame } from "../game/GameProvider";

export function ListenScreen(): JSX.Element | null {
  const { session, playReferenceEnded } = useGame();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [played, setPlayed] = useState(false);
  const [ended, setEnded] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);

  useEffect(() => {
    if (!played || ended) return;
    let frameId = 0;
    const tick = () => {
      const audio = audioRef.current;
      if (audio) setCurrentMs(audio.currentTime * 1000);
      frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [played, ended]);

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
      <HostNarration sessionId={session.id} cue="listen" />
      {!played ? <LyricsPrompt lyrics={session.song.expectedLyrics} /> : null}

      <audio ref={audioRef} src={mediaUrl(session.song.fullMixUrl)} onEnded={handleEnded} />

      {!played && (
        <button type="button" className="primary-button primary-button-large" onClick={handlePlay}>
          Play Reference Clip
        </button>
      )}
      {played && !ended ? (
        <>
          <p className="playing-indicator">Playing the reference clip...</p>
          <LyricDisplay lines={session.song.lyricLines} currentMs={currentMs} />
        </>
      ) : null}
      {ended && <p className="playing-indicator">Starting the first turn...</p>}
    </section>
  );
}
