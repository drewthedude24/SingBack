import { useMemo, useState, type FormEvent } from "react";

import { useGame } from "../game/GameProvider";

function validateNames(names: string[]): string | null {
  const trimmed = names.map((name) => name.trim());
  if (trimmed.some((name) => name.length === 0)) {
    return "Every player needs a name.";
  }
  if (trimmed.some((name) => name.length > 30)) {
    return "Player names must be 30 characters or fewer.";
  }
  const unique = new Set(trimmed.map((name) => name.toLowerCase()));
  if (unique.size !== trimmed.length) {
    return "Player names must be unique.";
  }
  return null;
}

export function LobbyScreen(): JSX.Element {
  const { songs, songsLoading, startRound, busy } = useGame();
  const [names, setNames] = useState(["", "", ""]);
  const [validationError, setValidationError] = useState<string | null>(null);

  const readySongs = useMemo(() => songs.filter((song) => song.ready), [songs]);

  function updatePlayerCount(count: number) {
    setNames((previous) =>
      Array.from({ length: count }, (_, index) => previous[index] ?? ""),
    );
  }

  function updateName(index: number, value: string) {
    setNames((previous) => previous.map((name, i) => (i === index ? value : name)));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const error = validateNames(names);
    if (error) {
      setValidationError(error);
      return;
    }
    if (readySongs.length === 0) {
      setValidationError("No prepared songs are ready yet.");
      return;
    }
    const randomIndex = Math.floor(Math.random() * readySongs.length);
    const randomSongId = readySongs[randomIndex].id;
    setValidationError(null);
    void startRound(
      names.map((name) => name.trim()),
      randomSongId,
    );
  }

  return (
    <section className="screen lobby-screen">
      <h1>Lobby</h1>
      <p className="tagline">Choose the group size. SingBack secretly draws one licensed clip when the round starts.</p>

      <form className="lobby-form" onSubmit={handleSubmit}>
        <fieldset>
          <legend>How many players?</legend>
          <div className="player-count-picker" role="group" aria-label="Player count">
            {[1, 2, 3, 4].map((count) => (
              <button
                key={count}
                type="button"
                className={`player-count-button${names.length === count ? " player-count-button-selected" : ""}`}
                aria-pressed={names.length === count}
                onClick={() => updatePlayerCount(count)}
              >
                {count}
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>Player names</legend>
          {names.map((name, index) => (
            <label key={index} className="field">
              Player {index + 1}
              <input
                type="text"
                value={name}
                maxLength={30}
                onChange={(event) => updateName(index, event.target.value)}
                placeholder={`Player ${index + 1} name`}
                required
              />
            </label>
          ))}
        </fieldset>

        <fieldset className="mystery-song-fieldset">
          <legend>Mystery song</legend>
          {songsLoading && <p>Loading songs...</p>}
          {!songsLoading && readySongs.length === 0 && (
            <p className="field-error">
              No prepared songs are ready yet. Run scripts/validate_song_assets.py on the backend.
            </p>
          )}
          {!songsLoading && readySongs.length > 0 ? (
            <p className="mystery-song-copy">
              A prepared vocal challenge will be picked at random after you continue.
            </p>
          ) : null}
        </fieldset>

        {validationError ? <p className="field-error">{validationError}</p> : null}

        <button
          type="submit"
          className="primary-button surprise-button"
          disabled={busy || readySongs.length === 0}
        >
          {busy ? "Choosing your song..." : "Surprise Me & Start Round"}
        </button>
      </form>
    </section>
  );
}
