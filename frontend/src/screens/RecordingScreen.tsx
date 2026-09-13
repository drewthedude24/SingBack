import { useEffect, useState } from "react";

import { LyricDisplay } from "../components/LyricDisplay";
import { Waveform } from "../components/Waveform";
import { useGame } from "../game/GameProvider";

export function RecordingScreen(): JSX.Element {
  const {
    session,
    currentPlayer,
    stopRecordingEarly,
    recorderAnalyser,
    songAnalyser,
    getPlaybackClockSec,
    turnClock,
  } = useGame();
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!turnClock) return;
    let frameId = 0;
    const tick = () => {
      const elapsedSec = getPlaybackClockSec() - turnClock.startAudioSec;
      setElapsedMs(Math.max(0, Math.min(turnClock.durationMs, elapsedSec * 1000)));
      frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [getPlaybackClockSec, turnClock]);

  const durationMs = turnClock?.durationMs ?? 0;
  const remainingSeconds = Math.max(0, Math.ceil((durationMs - elapsedMs) / 1000));
  const progress = durationMs > 0 ? Math.min(100, (elapsedMs / durationMs) * 100) : 0;
  return (
    <section className="screen recording-screen">
      <p className="eyebrow">Recording {currentPlayer?.displayName}</p>
      <div className="recording-indicator" aria-hidden="true" />
      <h1>Sing it back!</h1>
      <p className="tagline">The instrumental is playing. Recording stops automatically when it ends.</p>
      {session ? <LyricDisplay lines={session.song.lyricLines} currentMs={elapsedMs} /> : null}

      <div className="waveform-pair">
        <div className="waveform-slot">
          <span className="waveform-label">Instrumental</span>
          <Waveform analyser={songAnalyser} color="#35e2c9" />
        </div>
        <div className="waveform-slot">
          <span className="waveform-label">Your live voice</span>
          <Waveform analyser={recorderAnalyser} color="#ff5da2" />
        </div>
      </div>

      <div className="clip-progress" role="progressbar" aria-valuenow={Math.round(progress)}>
        <div className="clip-progress-track">
          <div className="clip-progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <span className="clip-progress-remaining">{remainingSeconds}s left</span>
      </div>
      <button type="button" className="secondary-button" onClick={() => void stopRecordingEarly()}>
        Stop early
      </button>
    </section>
  );
}
