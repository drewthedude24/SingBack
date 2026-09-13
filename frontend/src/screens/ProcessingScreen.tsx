import { useEffect, useRef } from "react";

import { Spinner } from "../components/Spinner";
import { useGame } from "../game/GameProvider";

export function ProcessingScreen(): JSX.Element {
  const { retryProcessing, error, busy } = useGame();
  const startedRef = useRef(false);

  useEffect(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    void retryProcessing();
  }, [retryProcessing]);

  return (
    <section className="screen processing-screen">
      <Spinner label="Scoring every performance and preparing the reveal..." />
      {error && !busy ? (
        <button type="button" className="primary-button" onClick={() => void retryProcessing()}>
          Try again
        </button>
      ) : null}
    </section>
  );
}
