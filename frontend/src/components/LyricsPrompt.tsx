interface LyricsPromptProps {
  lyrics: string;
}

export function LyricsPrompt({ lyrics }: LyricsPromptProps): JSX.Element {
  return (
    <aside className="lyrics-prompt" aria-label="Lyrics to sing">
      <span className="lyrics-label">Your lyric cue</span>
      <p>&ldquo;{lyrics}&rdquo;</p>
    </aside>
  );
}
