import { useEffect, useRef, useState } from "react";

import { mediaUrl } from "../api/client";
import type { SessionSong } from "../api/types";
import { InstrumentalPlayer } from "../audio/playback";
import { fileFromRecording, requestMicrophone, TurnRecorder } from "../audio/recorder";
import { LiveRecordingEvidence, preloadReferenceWaveform } from "../components/LiveRecordingEvidence";
import { LyricDisplay } from "../components/LyricDisplay";
import { LyricsPrompt } from "../components/LyricsPrompt";
import { rooms, type Membership, type RoomView } from "./api";

type CaptureStage = "idle" | "preparing" | "countdown" | "recording" | "uploading" | "retry";

export function OnlineRecording({ member, song, onUploaded }: {
  member: Membership; song: SessionSong; onUploaded: (room: RoomView) => void;
}): JSX.Element {
  const [stage, setStage] = useState<CaptureStage>("idle");
  const [countdown, setCountdown] = useState(3);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const engine = useRef<InstrumentalPlayer | null>(null);
  const recorder = useRef<TurnRecorder | null>(null);
  const pending = useRef<FormData | null>(null);
  const active = useRef(true);
  const busy = useRef(false);
  const playbackStart = useRef(0);
  const raf = useRef(0);

  useEffect(() => {
    active.current = true;
    void preloadReferenceWaveform(mediaUrl(song.referenceVocalUrl)).catch(() => {});
    return () => {
      active.current = false;
      engine.current?.stop();
      void engine.current?.close();
      cancelAnimationFrame(raf.current);
      const current = recorder.current;
      recorder.current = null;
      if (current) void current.stop().catch(() => {});
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, [song.referenceVocalUrl]);

  function releaseMic() {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }

  async function upload(form: FormData) {
    pending.current = form;
    setStage("uploading");
    try {
      const room = await rooms.upload(member, form);
      pending.current = null;
      if (active.current) onUploaded(room);
    } catch (err) {
      if (active.current) {
        setError(err instanceof Error ? err.message : "Upload failed. Your recording is saved on this page for retry.");
        setStage("retry");
      }
    } finally { busy.current = false; }
  }

  async function finish(current: TurnRecorder, preroll: number) {
    if (recorder.current !== current) return;
    recorder.current = null;
    engine.current?.stop();
    cancelAnimationFrame(raf.current);
    setAnalyser(null);
    const recording = await current.stop();
    releaseMic();
    if (!active.current) return;
    const form = new FormData();
    form.append("file", fileFromRecording(recording.blob, recording.mimeType));
    form.append("mimeType", recording.mimeType);
    form.append("prerollMs", String(preroll));
    form.append("durationMs", String(Math.max(1, Math.round(recording.durationMs))));
    await upload(form);
  }

  const preroll = useRef(0);

  async function begin() {
    if (busy.current) return;
    busy.current = true;
    setError(null);
    setStage("preparing");
    try {
      // Resume Web Audio during the tap: mobile browsers require a gesture.
      engine.current ??= new InstrumentalPlayer();
      await engine.current.resume();
      const bufferPromise = engine.current.preload(mediaUrl(song.instrumentalUrl));
      stream.current = await requestMicrophone();
      const buffer = await bufferPromise;
      if (!active.current) { releaseMic(); return; }
      setStage("countdown");
      for (let left = 3; left > 0; left -= 1) {
        setCountdown(left);
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        if (!active.current) return;
      }
      const current = new TurnRecorder(stream.current, engine.current.audioContext);
      recorder.current = current;
      const started = await current.start();
      if (!active.current) return;
      const clockPerf = performance.now();
      const clockAudio = engine.current.currentTime;
      const scheduled = clockAudio + 0.5;
      preroll.current = Math.round(clockPerf + (scheduled - clockAudio) * 1000 - started);
      playbackStart.current = scheduled;
      setAnalyser(current.getAnalyser());
      const { onEnded } = engine.current.schedule(buffer, scheduled);
      setStage("recording");
      const tick = () => {
        setElapsed(Math.max(0, Math.min(song.durationMs, ((engine.current?.currentTime ?? 0) - playbackStart.current) * 1000)));
        raf.current = requestAnimationFrame(tick);
      };
      raf.current = requestAnimationFrame(tick);
      await onEnded;
      await new Promise((resolve) => window.setTimeout(resolve, 400));
      if (active.current) await finish(current, preroll.current);
    } catch (err) {
      engine.current?.stop();
      const current = recorder.current;
      recorder.current = null;
      if (current) await current.stop().catch(() => {});
      releaseMic();
      cancelAnimationFrame(raf.current);
      busy.current = false;
      if (active.current) {
        setStage("idle");
        setError(err instanceof Error ? err.message : "Could not start recording. Check microphone permission.");
      }
    }
  }

  return <div className="online-turn">
    <p className="eyebrow">Your turn</p>
    <h1>{stage === "countdown" ? countdown : stage === "recording" ? "Sing it back!" : "Take the stage"}</h1>
    {error ? <p role="alert" className="field-error">{error}</p> : null}
    {stage === "idle" ? <>
      <p>Your mic records only your voice. The instrumental plays on this device. Headphones help keep the recording clean.</p>
      <LyricsPrompt lyrics={song.expectedLyrics} />
      <button className="primary-button primary-button-large" onClick={() => void begin()}>Start my turn</button>
    </> : null}
    {stage === "preparing" ? <p role="status">Preparing audio and microphone…</p> : null}
    {stage === "recording" ? <>
      <LyricDisplay lines={song.lyricLines} currentMs={elapsed} />
      <LiveRecordingEvidence referenceVocalUrl={mediaUrl(song.referenceVocalUrl)} analyser={analyser}
        currentMs={elapsed} durationMs={song.durationMs} />
      <p>{Math.max(0, Math.ceil((song.durationMs - elapsed) / 1000))}s left</p>
      <button className="secondary-button" onClick={() => {
        const current = recorder.current;
        if (current) void finish(current, preroll.current);
      }}>Stop early &amp; submit</button>
    </> : null}
    {stage === "uploading" ? <p role="status">Uploading your performance. Grading starts immediately in the background…</p> : null}
    {stage === "retry" ? <button className="primary-button" onClick={() => {
      if (!busy.current && pending.current) { busy.current = true; setError(null); void upload(pending.current); }
    }}>Retry my saved recording</button> : null}
  </div>;
}
