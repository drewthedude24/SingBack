import { useGame } from "../game/GameProvider";

export function ErrorBanner(): JSX.Element | null {
  const { error, dismissError } = useGame();
  if (!error) return null;

  return (
    <div className="error-banner" role="alert">
      <span>{error.message}</span>
      {error.retryable ? <span className="error-hint">You can try again.</span> : null}
      <button type="button" className="error-dismiss" onClick={dismissError}>
        Dismiss
      </button>
    </div>
  );
}
