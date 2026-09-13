import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, ApiRequestError, instrumentalUrlForSong, mediaUrl } from "../api/client";
import type {
  FinalResults,
  PlayerPublic,
  RecordingResponse,
  RecordingTiming,
  RevealResults,
  SessionView,
  SongPublic,
} from "../api/types";
import { InstrumentalPlayer } from "../audio/playback";
import { fileFromRecording, requestMicrophone, TurnRecorder } from "../audio/recorder";
import { preloadReferenceWaveform } from "../components/LiveRecordingEvidence";
import type { EngineError, Stage } from "./types";

const COUNTDOWN_SECONDS = 3;
/** How far ahead of the scheduled instrumental start capture must begin. */
const PREROLL_LEAD_SECONDS = 0.5;
/** Safety margin added after the instrumental ends before the recorder is stopped. */
const RECORDING_TAIL_MS = 400;

interface GameEngine {
  stage: Stage;
  songs: SongPublic[];
  songsLoading: boolean;
  session: SessionView | null;
  micReady: boolean;
  micError: string | null;
  countdownValue: number;
  lastRecording: RecordingResponse | null;
  revealResults: RevealResults | null;
  revealIndex: number;
  playedRevealIds: string[];
  finalResults: FinalResults | null;
  error: EngineError | null;
  busy: boolean;

  currentPlayer: PlayerPublic | null;
  nextPlayerForHandoff: PlayerPublic | null;
  recorderAnalyser: AnalyserNode | null;
  getPlaybackClockSec: () => number;
  turnClock: { startAudioSec: number; durationMs: number } | null;

  enableMicrophone: () => Promise<void>;
  goToLobby: () => void;
  loadSongs: () => Promise<void>;
  startRound: (playerNames: string[], songId: string) => Promise<void>;
  playReferenceEnded: () => Promise<void>;
  beginTurn: () => Promise<void>;
  stopRecordingEarly: () => Promise<void>;
  continueAfterHandoff: () => Promise<void>;
  retryProcessing: () => Promise<void>;
  advanceReveal: () => void;
  finishReveal: () => Promise<void>;
  playAgain: () => void;
  dismissError: () => void;
}

const GameContext = createContext<GameEngine | null>(null);

export function useGame(): GameEngine {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error("useGame must be used within a GameProvider");
  }
  return context;
}

export function GameProvider({ children }: { children: ReactNode }): JSX.Element {
  const [stage, setStage] = useState<Stage>("home");
  const [songs, setSongs] = useState<SongPublic[]>([]);
  const [songsLoading, setSongsLoading] = useState(false);
  const [session, setSession] = useState<SessionView | null>(null);
  const [micReady, setMicReady] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [countdownValue, setCountdownValue] = useState(COUNTDOWN_SECONDS);
  const [lastRecording, setLastRecording] = useState<RecordingResponse | null>(null);
  const [revealResults, setRevealResults] = useState<RevealResults | null>(null);
  const [revealIndex, setRevealIndex] = useState(0);
  const [playedRevealIds, setPlayedRevealIds] = useState<string[]>([]);
  const [finalResults, setFinalResults] = useState<FinalResults | null>(null);
  const [error, setError] = useState<EngineError | null>(null);
  const [busy, setBusy] = useState(false);
  const [recorderAnalyser, setRecorderAnalyser] = useState<AnalyserNode | null>(null);
  const [turnClock, setTurnClock] = useState<{
    startAudioSec: number;
    durationMs: number;
  } | null>(null);

  const micStreamRef = useRef<MediaStream | null>(null);
  const audioEngineRef = useRef<InstrumentalPlayer | null>(null);
  const activeRecorderRef = useRef<TurnRecorder | null>(null);
  const pendingTimingRef = useRef<RecordingTiming | null>(null);
  const finalizeInFlightRef = useRef(false);

  function getAudioEngine(): InstrumentalPlayer {
    if (!audioEngineRef.current) {
      audioEngineRef.current = new InstrumentalPlayer();
    }
    return audioEngineRef.current;
  }

  const handleApiError = useCallback((err: unknown) => {
    if (err instanceof ApiRequestError) {
      setError({ message: err.message, retryable: err.retryable, code: err.code });
    } else if (err instanceof Error) {
      setError({ message: err.message, retryable: false });
    } else {
      setError({ message: "Something unexpected went wrong.", retryable: false });
    }
  }, []);

  const dismissError = useCallback(() => setError(null), []);

  const enableMicrophone = useCallback(async () => {
    setMicError(null);
    try {
      const stream = await requestMicrophone();
      micStreamRef.current = stream;
      setMicReady(true);
      await getAudioEngine().resume();
    } catch {
      setMicReady(false);
      setMicError(
        "Microphone access was denied. Allow microphone access in your browser's site settings, then try again.",
      );
    }
  }, []);

  const loadSongs = useCallback(async () => {
    setSongsLoading(true);
    try {
      const list = await api.songs();
      setSongs(list);
    } catch (err) {
      handleApiError(err);
    } finally {
      setSongsLoading(false);
    }
  }, [handleApiError]);

  const goToLobby = useCallback(() => {
    setStage("lobby");
    void loadSongs();
  }, [loadSongs]);

  const startRound = useCallback(
    async (playerNames: string[], songId: string) => {
      setBusy(true);
      setError(null);
      try {
        const created = await api.createSession(playerNames, songId);
        const started = await api.startSession(created.id);
        void preloadReferenceWaveform(mediaUrl(started.song.referenceVocalUrl));
        setSession(started);
        setStage("listen");
      } catch (err) {
        handleApiError(err);
      } finally {
        setBusy(false);
      }
    },
    [handleApiError],
  );

  const playReferenceEnded = useCallback(async () => {
    if (!session) return;
    setBusy(true);
    try {
      const updated = await api.referenceComplete(session.id);
      setSession(updated);
      setStage("turn-intro");
    } catch (err) {
      handleApiError(err);
    } finally {
      setBusy(false);
    }
  }, [session, handleApiError]);

  const submitRecording = useCallback(
    async (result: { blob: Blob; mimeType: string; durationMs: number }) => {
      const timing = pendingTimingRef.current;
      if (!session || !timing || !session.currentPlayerId) return;
      setStage("uploading");
      setError(null);
      try {
        const form = new FormData();
        form.append("file", fileFromRecording(result.blob, result.mimeType));
        form.append("playerId", session.currentPlayerId);
        form.append("mimeType", result.mimeType);
        form.append("recordingStartPerfMs", String(timing.recordingStartPerfMs));
        form.append("clockSamplePerfMs", String(timing.clockSamplePerfMs));
        form.append("clockSampleAudioSec", String(timing.clockSampleAudioSec));
        form.append("plannedPlaybackAudioSec", String(timing.plannedPlaybackAudioSec));
        form.append("prerollMs", String(timing.prerollMs));
        form.append("durationMs", String(result.durationMs));
        form.append("isDemoFixture", "false");

        const response = await api.uploadRecording(session.id, form);
        setLastRecording(response);
        pendingTimingRef.current = null;

        if (response.nextPhase === "NEXT_PLAYER") {
          setStage("handoff");
        } else {
          setStage("processing");
        }
      } catch (err) {
        handleApiError(err);
        setStage("turn-intro");
      }
    },
    [session, handleApiError],
  );

  const beginTurn = useCallback(async () => {
    if (!session || !micStreamRef.current) {
      setError({
        message: "Microphone access is required to record a turn.",
        retryable: false,
      });
      return;
    }
    setError(null);
    setCountdownValue(COUNTDOWN_SECONDS);
    setStage("countdown");

    try {
      const engine = getAudioEngine();
      await engine.resume();
      const instrumentalUrl = instrumentalUrlForSong(session.song);
      const bufferPromise = engine.preload(instrumentalUrl);

      await new Promise<void>((resolve) => {
        let remaining = COUNTDOWN_SECONDS;
        const tick = () => {
          remaining -= 1;
          setCountdownValue(remaining);
          if (remaining <= 0) {
            resolve();
          } else {
            setTimeout(tick, 1000);
          }
        };
        setTimeout(tick, 1000);
      });

      const buffer = await bufferPromise;

      const recorder = new TurnRecorder(micStreamRef.current);
      activeRecorderRef.current = recorder;
      setRecorderAnalyser(recorder.getAnalyser());

      const recordingStartPerfMs = await recorder.start();
      const clockSamplePerfMs = performance.now();
      const clockSampleAudioSec = engine.currentTime;
      const plannedPlaybackAudioSec = clockSampleAudioSec + PREROLL_LEAD_SECONDS;
      const plannedPlaybackPerfMs =
        clockSamplePerfMs + (plannedPlaybackAudioSec - clockSampleAudioSec) * 1000;
      const prerollMs = Math.round(plannedPlaybackPerfMs - recordingStartPerfMs);

      pendingTimingRef.current = {
        recordingStartPerfMs,
        clockSamplePerfMs,
        clockSampleAudioSec,
        plannedPlaybackAudioSec,
        prerollMs,
      };

      setTurnClock({
        startAudioSec: plannedPlaybackAudioSec,
        durationMs: session.song.durationMs,
      });

      const { onEnded } = engine.schedule(buffer, plannedPlaybackAudioSec);
      setStage("recording");
      await onEnded;
      await new Promise((resolve) => setTimeout(resolve, RECORDING_TAIL_MS));

      if (activeRecorderRef.current !== recorder) return;
      activeRecorderRef.current = null;
      setRecorderAnalyser(null);
      setTurnClock(null);
      const result = await recorder.stop();
      await submitRecording(result);
    } catch (err) {
      audioEngineRef.current?.stop();
      const recorder = activeRecorderRef.current;
      activeRecorderRef.current = null;
      pendingTimingRef.current = null;
      setRecorderAnalyser(null);
      setTurnClock(null);
      if (recorder) {
        try {
          await recorder.stop();
        } catch {
          // Preserve the original setup/playback error for the user.
        }
      }
      handleApiError(err);
      setStage("turn-intro");
    }
  }, [session, submitRecording, handleApiError]);

  const stopRecordingEarly = useCallback(async () => {
    const recorder = activeRecorderRef.current;
    if (!recorder) return;
    audioEngineRef.current?.stop();
    activeRecorderRef.current = null;
    setRecorderAnalyser(null);
    setTurnClock(null);
    try {
      const result = await recorder.stop();
      await submitRecording(result);
    } catch (err) {
      handleApiError(err);
      setStage("turn-intro");
    }
  }, [submitRecording, handleApiError]);

  const getPlaybackClockSec = useCallback(
    () => audioEngineRef.current?.currentTime ?? 0,
    [],
  );

  const continueAfterHandoff = useCallback(async () => {
    if (!session) return;
    setBusy(true);
    try {
      const updated = await api.nextPlayer(session.id);
      setSession(updated);
      setStage("turn-intro");
    } catch (err) {
      handleApiError(err);
    } finally {
      setBusy(false);
    }
  }, [session, handleApiError]);

  const retryProcessing = useCallback(async () => {
    if (!session || finalizeInFlightRef.current) return;
    finalizeInFlightRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const results = await api.finalize(session.id);
      setRevealResults(results);
      setSession((prev) => (prev ? { ...prev, phase: "REVEAL" } : prev));
      setRevealIndex(0);
      setPlayedRevealIds([]);
      setStage("reveal");
    } catch (err) {
      if (err instanceof ApiRequestError && err.code === "INVALID_SESSION_PHASE") {
        try {
          const results = await api.results(session.id);
          setRevealResults(results);
          setSession((prev) => (prev ? { ...prev, phase: "REVEAL" } : prev));
          setRevealIndex(0);
          setPlayedRevealIds([]);
          setStage("reveal");
        } catch (innerErr) {
          handleApiError(innerErr);
        }
      } else {
        handleApiError(err);
      }
    } finally {
      finalizeInFlightRef.current = false;
      setBusy(false);
    }
  }, [session, handleApiError]);

  const advanceReveal = useCallback(() => {
    if (!revealResults) return;
    const current = revealResults.performances[revealIndex];
    if (current) {
      setPlayedRevealIds((ids) => (ids.includes(current.revealId) ? ids : [...ids, current.revealId]));
    }
    setRevealIndex((index) => Math.min(index + 1, revealResults.performances.length - 1));
  }, [revealResults, revealIndex]);

  const finishReveal = useCallback(async () => {
    if (!session || !revealResults) return;
    const current = revealResults.performances[revealIndex];
    const allPlayed = current
      ? [...new Set([...playedRevealIds, current.revealId])]
      : playedRevealIds;

    setBusy(true);
    setError(null);
    try {
      const allIds = revealResults.performances.map((performance) => performance.revealId);
      const updated = await api.revealComplete(session.id, allIds);
      setSession(updated);
      setPlayedRevealIds(allPlayed);
      const final = await api.finalResults(session.id);
      setFinalResults(final);
      setStage("results");
    } catch (err) {
      handleApiError(err);
    } finally {
      setBusy(false);
    }
  }, [session, revealResults, revealIndex, playedRevealIds, handleApiError]);

  const playAgain = useCallback(() => {
    window.location.reload();
  }, []);

  const currentPlayer = useMemo(() => {
    if (!session) return null;
    return session.players.find((player) => player.id === session.currentPlayerId) ?? null;
  }, [session]);

  const nextPlayerForHandoff = useMemo(() => {
    if (!session || !session.currentPlayerId) return null;
    const index = session.players.findIndex((player) => player.id === session.currentPlayerId);
    if (index < 0) return null;
    return session.players[index + 1] ?? null;
  }, [session]);

  const value: GameEngine = {
    stage,
    songs,
    songsLoading,
    session,
    micReady,
    micError,
    countdownValue,
    lastRecording,
    revealResults,
    revealIndex,
    playedRevealIds,
    finalResults,
    error,
    busy,
    currentPlayer,
    nextPlayerForHandoff,
    recorderAnalyser,
    getPlaybackClockSec,
    turnClock,
    enableMicrophone,
    goToLobby,
    loadSongs,
    startRound,
    playReferenceEnded,
    beginTurn,
    stopRecordingEarly,
    continueAfterHandoff,
    retryProcessing,
    advanceReveal,
    finishReveal,
    playAgain,
    dismissError,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
}
