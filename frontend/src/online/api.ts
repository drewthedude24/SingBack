import { request } from "../api/client";
import type { AnalysisProgress, FinalResults, NarrationCue, NarrationResponse, SessionSong } from "../api/types";

export interface RoomPlayer {
  id: string;
  displayName: string;
  isHost: boolean;
  ready: boolean;
  listened: boolean;
  connected: boolean;
  recorded: boolean;
}

export interface RoomView {
  code: string;
  phase: "LOBBY" | "LISTEN" | "TURN_INTRO" | "PROCESSING" | "RESULTS" | "CLOSED";
  roundNumber: number;
  meId: string;
  players: RoomPlayer[];
  song: SessionSong | null;
  currentPlayerId: string | null;
  progress: AnalysisProgress | null;
  results: FinalResults | null;
  error: string | null;
}

export interface Membership { code: string; token: string }
export interface Credentials extends Membership { room: RoomView }

const headers = (member: Membership) => ({ Authorization: `Bearer ${member.token}` });
const path = (member: Membership) => `/api/rooms/${encodeURIComponent(member.code)}`;

export const rooms = {
  create: (displayName: string) => request<Credentials>("/api/rooms", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ displayName }),
  }),
  join: (code: string, displayName: string) => request<Credentials>(`/api/rooms/${encodeURIComponent(code.toUpperCase())}/join`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ displayName }),
  }),
  get: (member: Membership) => request<RoomView>(path(member), { headers: headers(member), cache: "no-store" }),
  ready: (member: Membership, ready: boolean) => request<RoomView>(`${path(member)}/ready`, {
    method: "POST", headers: { ...headers(member), "Content-Type": "application/json" }, body: JSON.stringify({ ready }),
  }),
  action: (member: Membership, action: "start" | "listened" | "skip" | "retry" | "rematch") =>
    request<RoomView>(`${path(member)}/${action}`, { method: "POST", headers: headers(member) }),
  upload: (member: Membership, form: FormData) => request<RoomView>(`${path(member)}/recordings`, {
    method: "POST", headers: headers(member), body: form,
  }),
  leave: (member: Membership) => request<void>(`${path(member)}/leave`, { method: "POST", headers: headers(member) }),
  remove: (member: Membership, playerId: string) => request<RoomView>(`${path(member)}/players/${encodeURIComponent(playerId)}`, {
    method: "DELETE", headers: headers(member),
  }),
  narration: (member: Membership, cue: NarrationCue) => request<NarrationResponse>(`${path(member)}/narration/${cue}`, {
    headers: headers(member),
  }),
};
