export function PlayerChip({
  name,
  active,
}: {
  name: string;
  active?: boolean;
}): JSX.Element {
  return (
    <span className={`player-chip${active ? " player-chip-active" : ""}`}>
      <span className="player-chip-avatar" style={{ background: colorFor(name) }}>
        {name.charAt(0).toUpperCase()}
      </span>
      {name}
    </span>
  );
}
const AVATAR_COLORS = ["#ff5da2", "#7c5cff", "#35e2c9", "#f4c542"];

function colorFor(name: string): string {
  return AVATAR_COLORS[(name.charCodeAt(0) || 0) % AVATAR_COLORS.length];
}
