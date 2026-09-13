import type { LyricLine } from "../api/types";

interface LyricDisplayProps {
  lines: LyricLine[];
  currentMs: number;
}

export function LyricDisplay({ lines, currentMs }: LyricDisplayProps): JSX.Element | null {
  if (lines.length === 0) return null;
  return (
    <div className="lyric-display" aria-label="Lyrics to sing">
      {lines.map((line, index) => {
        const active = currentMs >= line.startMs && currentMs < line.endMs;
        const past = currentMs >= line.endMs;
        return (
          <p
            key={`${line.startMs}-${index}`}
            className={`lyric-line${active ? " lyric-line-active" : ""}${
              past ? " lyric-line-past" : ""
            }`}
          >
            {line.text}
          </p>
        );
      })}
    </div>
  );
}
