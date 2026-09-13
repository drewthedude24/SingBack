/**
 * Backend phases (LOBBY, LISTEN, TURN_INTRO, NEXT_PLAYER, PROCESSING, REVEAL,
 * RESULTS) are authoritative and live on SessionView.phase. Stage adds
 * the purely local sub-steps the integration contract explicitly leaves to the
 * frontend (countdown, recording, uploading, the between-player handoff) plus
 * two pre-session steps (home, lobby).
 */
export type Stage =
  | "home"
  | "lobby"
  | "listen"
  | "turn-intro"
  | "countdown"
  | "recording"
  | "uploading"
  | "handoff"
  | "processing"
  | "reveal"
  | "results";

export interface EngineError {
  message: string;
  retryable: boolean;
  code?: string;
}
