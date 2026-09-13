export function Countdown({ value }: { value: number }): JSX.Element {
  return (
    <div className="countdown" aria-live="assertive">
      {value > 0 ? value : "Sing!"}
    </div>
  );
}
