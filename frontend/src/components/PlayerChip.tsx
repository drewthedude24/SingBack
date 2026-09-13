export function PlayerChip({
  name,
  active,
}: {
  name: string;
  active?: boolean;
}): JSX.Element {
  return <span className={`player-chip${active ? " player-chip-active" : ""}`}>{name}</span>;
}
