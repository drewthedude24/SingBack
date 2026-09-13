// These types mirror backend/app/models.py field-for-field (camelCase aliases,
// since the API serializes with response_model_by_alias=True). Update both
// together whenever the Pydantic models change.

export type Phase =
  | "LOBBY"
  | "LISTEN"
  | "TURN_INTRO"
  | "NEXT_PLAYER"
  | "PROCESSING"
  | "REVEAL"
  | "VOTING"
  | "RESULTS";

export interface SongPublic {
  id: string;
  title: string;
  artist: string;
  durationMs: number;
  fullMixUrl: string;
  instrumentalUrl: string;
  expectedLyrics: string;
  ready: boolean;
}

export interface PlayerPublic {
  id: string;
  displayName: string;
  turnOrder: number;
}

export interface SessionSong {
  id: string;
  title: string;
  durationMs: number;
  fullMixUrl: string;
  instrumentalUrl: string;
  expectedLyrics: string;
}

export interface SessionView {
  id: string;
  phase: Phase;
  song: SessionSong;
  players: PlayerPublic[];
  currentPlayerId: string | null;
  allArtifactsReady: boolean;
}

export interface RecordingResponse {
  recordingId: string;
  status: string;
  rawUrl: string | null;
  mixUrl: string;
  detectedDurationMs: number;
  appliedOffsetMs: number;
  silent: boolean;
  nextPhase: Phase;
}

export interface Score {
  pitch: number | null;
  rhythm: number | null;
  lyrics: number | null;
  completion: number;
  technicalTotal: number;
  scoringProfile: string;
  confidence: Record<string, string>;
  diagnostics: Record<string, string | number | null>;
}

export interface Feedback {
  summary: string;
  strength: string;
  improvement: string;
  announcerLine: string;
  tags: string[];
  source: string;
}

export interface RevealPerformance {
  revealId: string;
  mixUrl: string;
  score: Score;
  feedback: Feedback;
  detectedLyrics: string | null;
}

export interface RevealResults {
  sessionId: string;
  phase: Phase;
  performances: RevealPerformance[];
}

export interface VoteResponse {
  accepted: boolean;
  votesReceived: number;
  votesRequired: number;
  phase: Phase;
}

export interface FinalPerformance extends RevealPerformance {
  playerId: string;
  displayName: string;
  votes: number;
}

export interface FinalResults {
  sessionId: string;
  phase: Phase;
  performances: FinalPerformance[];
  technicalWinnerPlayerId: string;
  crowdFavoritePlayerId: string;
}

export interface HealthStatus {
  status: string;
  ffmpeg: boolean;
  gemini: string;
  elevenlabs: string;
}

export type NarrationCue = "listen" | "turn" | "processing" | "results";

export interface NarrationResponse {
  cue: NarrationCue;
  text: string;
  audioUrl: string | null;
  source: "elevenlabs" | "fallback";
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  retryable: boolean;
  details: Record<string, unknown>;
}

export interface ApiErrorBody {
  error: ApiErrorPayload;
}

export interface RecordingTiming {
  recordingStartPerfMs: number;
  clockSamplePerfMs: number;
  clockSampleAudioSec: number;
  plannedPlaybackAudioSec: number;
  prerollMs: number;
}
