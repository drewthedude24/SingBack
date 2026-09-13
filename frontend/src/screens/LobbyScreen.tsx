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
  const [songId, setSongId] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const readySongs = useMemo(() => songs.filter((song) => song.ready), [songs]);
  const selectedSongId = songId ?? readySongs[0]?.id ?? null;

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
    if (!selectedSongId) {
      setValidationError("Choose a song before starting the round.");
      return;
    }
    setValidationError(null);
    void startRound(
      names.map((name) => name.trim()),
      selectedSongId,
    );
  }

  return (
    <section className="screen lobby-screen">
      <h1>Lobby</h1>
      <p className="tagline">Every round is played by exactly three players, pass-and-play on one device.</p>

      <form className="lobby-form" onSubmit={handleSubmit}>
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

        <fieldset>
          <legend>Song</legend>
          {songsLoading && <p>Loading songs...</p>}
          {!songsLoading && readySongs.length === 0 && (
            <p className="field-error">
              No prepared songs are ready yet. Run scripts/validate_song_assets.py on the backend.
            </p>
          )}
          <div className="song-list">
            {readySongs.map((song) => (
              <label key={song.id} className={`song-option${selectedSongId === song.id ? " song-option-selected" : ""}`}>
                <input
                  type="radio"
                  name="song"
                  value={song.id}
                  checked={selectedSongId === song.id}
                  onChange={() => setSongId(song.id)}
                />
                <span className="song-title">{song.title}</span>
                <span className="song-artist">{song.artist}</span>
              </label>
            ))}
          </div>
        </fieldset>

        {validationError ? <p className="field-error">{validationError}</p> : null}

        <button
          type="submit"
          className="primary-button primary-button-large"
          disabled={busy || readySongs.length === 0}
        >
          {busy ? "Starting..." : "Start Round"}
        </button>
      </form>
    </section>
  );
}
