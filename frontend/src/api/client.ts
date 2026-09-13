import type {
  ApiErrorBody,
  FinalResults,
  HealthStatus,
  RecordingResponse,
  RevealResults,
  SessionSong,
  SessionView,
  SongPublic,
  VoteResponse,
} from "./types";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly details: Record<string, unknown>;

  constructor(status: number, payload: ApiErrorBody["error"]) {
    super(payload.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = payload.code;
    this.retryable = payload.retryable;
    this.details = payload.details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiRequestError(0, {
      code: "NETWORK_ERROR",
      message: "Could not reach the SingBack backend. Confirm it is running at " + API_BASE_URL,
      retryable: true,
      details: {},
    });
  }

  if (!response.ok) {
    let payload: ApiErrorBody | null = null;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      payload = null;
    }
    throw new ApiRequestError(
      response.status,
      payload?.error ?? {
        code: "UNKNOWN_ERROR",
        message: `Request failed with status ${response.status}.`,
        retryable: false,
        details: {},
      },
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function jsonInit(method: string, payload: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  songs: () => request<SongPublic[]>("/api/songs"),
  createSession: (playerNames: string[], songId: string) =>
    request<SessionView>("/api/sessions", jsonInit("POST", { playerNames, songId })),
  getSession: (sessionId: string) => request<SessionView>(`/api/sessions/${sessionId}`),
  startSession: (sessionId: string) =>
    request<SessionView>(`/api/sessions/${sessionId}/start`, { method: "POST" }),
  referenceComplete: (sessionId: string) =>
    request<SessionView>(`/api/sessions/${sessionId}/reference-complete`, { method: "POST" }),
  nextPlayer: (sessionId: string) =>
    request<SessionView>(`/api/sessions/${sessionId}/next-player`, { method: "POST" }),
  uploadRecording: (sessionId: string, form: FormData) =>
    request<RecordingResponse>(`/api/sessions/${sessionId}/recordings`, {
      method: "POST",
      body: form,
    }),
  finalize: (sessionId: string) =>
    request<RevealResults>(`/api/sessions/${sessionId}/finalize`, { method: "POST" }),
  results: (sessionId: string) => request<RevealResults>(`/api/sessions/${sessionId}/results`),
  revealComplete: (sessionId: string, revealIds: string[]) =>
    request<SessionView>(
      `/api/sessions/${sessionId}/reveal-complete`,
      jsonInit("POST", { revealIds }),
    ),
  vote: (sessionId: string, voterPlayerId: string, targetRevealId: string) =>
    request<VoteResponse>(
      `/api/sessions/${sessionId}/votes`,
      jsonInit("POST", { voterPlayerId, targetRevealId }),
    ),
  finalResults: (sessionId: string) =>
    request<FinalResults>(`/api/sessions/${sessionId}/results/final`),
};

/** Resolves a server-relative media path (e.g. "/media/songs/x/full.wav") against the API origin. */
export function mediaUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE_URL}${path}`;
}

/**
 * The API never hands the frontend an instrumental URL directly (only the full
 * reference mix). Every prepared song follows the same on-disk layout, so the
 * instrumental lives at the same path as the full mix with the filename swapped.
 */
export function instrumentalUrlForSong(song: SessionSong): string {
  return mediaUrl(song.fullMixUrl.replace(/full\.[a-zA-Z0-9]+$/, "instrumental.wav"));
}
