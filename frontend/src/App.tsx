import { ErrorBanner } from "./components/ErrorBanner";
import { PlayerChip } from "./components/PlayerChip";
import { GameProvider, useGame } from "./game/GameProvider";
import { CountdownScreen } from "./screens/CountdownScreen";
import { HandoffScreen } from "./screens/HandoffScreen";
import { HomeScreen } from "./screens/HomeScreen";
import { ListenScreen } from "./screens/ListenScreen";
import { LobbyScreen } from "./screens/LobbyScreen";
import { ProcessingScreen } from "./screens/ProcessingScreen";
import { RecordingScreen } from "./screens/RecordingScreen";
import { ResultsScreen } from "./screens/ResultsScreen";
import { RevealScreen } from "./screens/RevealScreen";
import { TurnIntroScreen } from "./screens/TurnIntroScreen";
import { UploadingScreen } from "./screens/UploadingScreen";

function CurrentScreen(): JSX.Element {
  const { stage } = useGame();

  switch (stage) {
    case "home":
      return <HomeScreen />;
    case "lobby":
      return <LobbyScreen />;
    case "listen":
      return <ListenScreen />;
    case "turn-intro":
      return <TurnIntroScreen />;
    case "countdown":
      return <CountdownScreen />;
    case "recording":
      return <RecordingScreen />;
    case "uploading":
      return <UploadingScreen />;
    case "handoff":
      return <HandoffScreen />;
    case "processing":
      return <ProcessingScreen />;
    case "reveal":
      return <RevealScreen />;
    case "results":
      return <ResultsScreen />;
    default:
      return <HomeScreen />;
  }
}

function PlayerRoster(): JSX.Element | null {
  const { session } = useGame();
  if (!session) return null;
  return (
    <div className="player-roster">
      {session.players.map((player) => (
        <PlayerChip
          key={player.id}
          name={player.displayName}
          active={player.id === session.currentPlayerId}
        />
      ))}
    </div>
  );
}

function AppShell(): JSX.Element {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-wordmark">SingBack</span>
        <PlayerRoster />
      </header>
      <ErrorBanner />
      <main className="app-main">
        <CurrentScreen />
      </main>
    </div>
  );
}

export function App(): JSX.Element {
  return (
    <GameProvider>
      <AppShell />
    </GameProvider>
  );
}
