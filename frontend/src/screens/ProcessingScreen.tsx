import { useEffect, useRef } from "react";

import { Spinner } from "../components/Spinner";
import { HostNarration } from "../components/HostNarration";
import { useGame } from "../game/GameProvider";

export function ProcessingScreen(): JSX.Element {
  const { session, retryProcessing, error, busy } = useGame();
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void retryProcessing();
  }, [retryProcessing]);

  return (
    <section className="screen processing-screen">
      <Spinner label="Scoring every performance and preparing the reveal..." />
      {session ? <HostNarration sessionId={session.id} cue="processing" /> : null}
      {error && !busy ? (
        <button type="button" className="primary-button" onClick={() => void retryProcessing()}>
          Try again
        </button>
      ) : null}
    </section>
  );
}
