import { useEffect, useRef, useState, type FormEvent } from "react";
import { QRCodeSVG } from "qrcode.react";

import { ApiRequestError, mediaUrl } from "../api/client";
import type { NarrationCue, NarrationResponse, SessionSong } from "../api/types";
import { requestMicrophone } from "../audio/recorder";
import { LyricDisplay } from "../components/LyricDisplay";
import { PerformanceCard } from "../components/PerformanceCard";
import { rooms, type Membership, type RoomView } from "./api";
import { OnlineRecording } from "./OnlineRecording";
import "./online.css";

const MEMBERSHIP_KEY = "singback-online-room";

export function savedMembership(): Membership | null {
  try {
    const raw = JSON.parse(sessionStorage.getItem(MEMBERSHIP_KEY) ?? "null") as Membership | null;
    const requested = new URLSearchParams(location.search).get("room")?.toUpperCase();
    return raw && (!requested || requested === raw.code) && /^[A-Z2-9]{6}$/.test(raw.code) && typeof raw.token === "string" ? raw : null;
  } catch { return null; }
}

function Narrator({ member, cue, turnKey }: { member: Membership; cue: NarrationCue; turnKey: string }): JSX.Element | null {
  const [narration, setNarration] = useState<NarrationResponse | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => {
    let active = true;
    void rooms.narration(member, cue).then((value) => { if (active) setNarration(value); }).catch(() => {});
    return () => { active = false; };
  }, [member, cue, turnKey]);
  useEffect(() => {
    const element = audio.current;
    return () => { element?.pause(); };
  }, [narration?.audioUrl]);
  if (!narration) return null;
  return <aside className="host-narration">
    <div><span className="host-narration-label">{narration.source === "elevenlabs" ? "ElevenLabs game host" : "Game host"}</span><p>{narration.text}</p></div>
    {narration.audioUrl ? <audio ref={audio} controls src={mediaUrl(narration.audioUrl)} aria-label="Play host narration" /> : null}
  </aside>;
}

function Listen({ song, done, onDone, busy }: { song: SessionSong; done: boolean; onDone: () => void; busy: boolean }): JSX.Element {
  const audio = useRef<HTMLAudioElement>(null);
  const [played, setPlayed] = useState(false);
  const [ended, setEnded] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const element = audio.current;
    return () => { element?.pause(); };
  }, []);
  async function play() {
    setError(null);
    try { await audio.current?.play(); setPlayed(true); }
    catch { setError("Audio could not start. Tap Play reference to try again."); }
  }
  return <>
    <p className="eyebrow">One listen. Make it count.</p><h1>{song.title}</h1>
    {done ? <p role="status">You’re ready. Waiting for everyone to finish listening…</p> : <>
      <p>Play the clip on your device. Turns begin after everyone has listened.</p>
      <audio ref={audio} src={mediaUrl(song.fullMixUrl)} preload="auto"
        onTimeUpdate={() => setCurrentMs((audio.current?.currentTime ?? 0) * 1000)}
        onEnded={() => { setEnded(true); onDone(); }}
        onError={() => setError("The clip could not load. Check your connection and try again.")} />
      {!played ? <button className="primary-button primary-button-large" disabled={busy} onClick={() => void play()}>Play reference</button> : null}
      {played ? <LyricDisplay lines={song.lyricLines} currentMs={currentMs} /> : null}
      {ended ? <button className="secondary-button" disabled={busy} onClick={onDone}>Continue to turns</button> : null}
      {error ? <p className="field-error" role="alert">{error}</p> : null}
    </>}
  </>;
}

export function OnlineGame({ onExit }: { onExit: () => void }): JSX.Element {
  const [member, setMember] = useState<Membership | null>(savedMembership);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [mode, setMode] = useState<"create" | "join">(() => new URLSearchParams(location.search).has("room") ? "join" : "create");
  const [code, setCode] = useState(() => new URLSearchParams(location.search).get("room")?.toUpperCase() ?? "");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connection, setConnection] = useState<string | null>(null);
  const [terminal, setTerminal] = useState(false);
  const [copied, setCopied] = useState(false);
  const busyRef = useRef(false);
  const sequence = useRef(0);

  function accept(next: RoomView) {
    setRoom((previous) => {
      if (previous && previous.code === next.code) {
        if (next.roundNumber < previous.roundNumber) return previous;
        if (next.roundNumber === previous.roundNumber) {
          // Ignore a stale poll returning after an action/upload response.
          const order = { LOBBY: 0, LISTEN: 1, TURN_INTRO: 2, PROCESSING: 3, RESULTS: 4, CLOSED: 5 };
          // RESULTS -> LOBBY is an intentional rematch transition.
          if (!(previous.phase === "RESULTS" && next.phase === "LOBBY") && order[next.phase] < order[previous.phase]) return previous;
          if (previous.phase === "TURN_INTRO" && next.phase === "TURN_INTRO") {
            const oldIndex = previous.players.findIndex((p) => p.id === previous.currentPlayerId);
            const newIndex = next.players.findIndex((p) => p.id === next.currentPlayerId);
            if (newIndex < oldIndex) return previous;
          }
        }
      }
      return next;
    });
  }

  useEffect(() => {
    if (!member || terminal) return;
    let cancelled = false;
    let timer = 0;
    const poll = async () => {
      if (!busyRef.current) {
        const requestNumber = sequence.current;
        try {
          const value = await rooms.get(member);
          if (!cancelled && requestNumber === sequence.current) { accept(value); setConnection(null); }
        } catch (err) {
          if (!cancelled) {
            if (err instanceof ApiRequestError && [401, 403, 404].includes(err.status)) {
              setTerminal(true); setError(err.message);
            } else setConnection("Connection interrupted. Reconnecting automatically… Keep this page open.");
          }
        }
      }
      if (!cancelled) timer = window.setTimeout(() => void poll(), 1000);
    };
    void poll();
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [member, terminal]);

  async function action(task: () => Promise<RoomView | void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    sequence.current += 1;
    setBusy(true); setError(null);
    try { const value = await task(); if (value) accept(value); }
    catch (err) { setError(err instanceof Error ? err.message : "Something went wrong. Please try again."); }
    finally { busyRef.current = false; setBusy(false); }
  }

  async function enter(event: FormEvent) {
    event.preventDefault();
    await action(async () => {
      const credentials = mode === "create" ? await rooms.create(name.trim()) : await rooms.join(code.trim(), name.trim());
      const membership = { code: credentials.code, token: credentials.token };
      try { sessionStorage.setItem(MEMBERSHIP_KEY, JSON.stringify(membership)); } catch { /* Private mode may block storage. */ }
      setMember(membership); setTerminal(false);
      history.replaceState(null, "", `${location.pathname}?room=${membership.code}`);
      return credentials.room;
    });
  }

  function clear() {
    sequence.current += 1;
    try { sessionStorage.removeItem(MEMBERSHIP_KEY); } catch { /* Best-effort cleanup. */ }
    setMember(null); setRoom(null); setTerminal(false); setError(null);
    history.replaceState(null, "", location.pathname);
    onExit();
  }

  async function leave() {
    const host = room?.players.find((p) => p.id === room.meId)?.isHost;
    if (room && room.phase !== "CLOSED" && !terminal && !window.confirm(host ? "End this room for everyone?" : "Leave this room?")) return;
    if (member && !terminal) await rooms.leave(member).catch(() => {});
    clear();
  }

  async function ready() {
    if (!member || !room) return;
    const me = room.players.find((p) => p.id === room.meId);
    await action(async () => {
      if (!me?.ready) {
        if (!navigator.mediaDevices?.getUserMedia) throw new Error("Microphone access needs HTTPS and a supported browser. Open the deployed link in Safari or Chrome.");
        const stream = await requestMicrophone();
        stream.getTracks().forEach((track) => track.stop());
      }
      return rooms.ready(member, !me?.ready);
    });
  }

  const me = room?.players.find((p) => p.id === room.meId);
  const current = room?.players.find((p) => p.id === room.currentPlayerId);
  const shareLink = member ? `${location.origin}${location.pathname}?room=${member.code}` : "";
  const winner = room?.results?.performances.find((p) => p.playerId === room.results?.technicalWinnerPlayerId);

  return <div className="app-shell online-shell">
    <header className="app-header"><span className="app-wordmark">SingBack <small>ONLINE</small></span>
      <button className="secondary-button" onClick={() => void leave()}>{member ? "Leave room" : "Back"}</button>
    </header>
    <main className="app-main">
      {error ? <p role="alert" className="online-alert">{error}</p> : null}
      {connection ? <p role="status" className="online-alert">{connection}</p> : null}
      {terminal ? <section className="screen"><h1>Let’s reconnect</h1><p>The room expired, the server restarted, or you were removed. Start or join a fresh room.</p>
        <button className="primary-button" onClick={clear}>Back to home</button></section> : !member ? <section className="screen online-entry">
        <p className="eyebrow">Different screens. Same stage.</p><h1>Your friends.<br />One song.</h1>
        <p>Join from phones or computers. No downloads, accounts, or API keys needed for players.</p>
        <div className="online-tabs" aria-label="Room options">
          <button className={mode === "create" ? "primary-button" : "secondary-button"} onClick={() => setMode("create")}>Host a room</button>
          <button className={mode === "join" ? "primary-button" : "secondary-button"} onClick={() => setMode("join")}>Join a room</button>
        </div>
        <form className="online-form" onSubmit={(event) => void enter(event)}>
          <label>Your name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={30} required autoComplete="nickname" placeholder="What should we call you?" /></label>
          {mode === "join" ? <label>Room code<input className="room-code-input" value={code} onChange={(event) => setCode(event.target.value.replace(/[^a-zA-Z2-9]/g, "").toUpperCase())} minLength={6} maxLength={6} required autoCapitalize="characters" autoComplete="off" placeholder="ABC234" /></label> : null}
          <button className="primary-button primary-button-large" disabled={busy || !name.trim()}>{busy ? "Connecting…" : mode === "create" ? "Create room" : "Join room"}</button>
        </form><p className="online-note">2–4 players · headphones recommended · each person needs a microphone</p>
      </section> : !room ? <section className="screen"><h1>Rejoining your room…</h1><p>Waking the server can take a moment on the free hosting plan.</p></section> : room.phase === "CLOSED" ? <section className="screen"><h1>The host ended this room.</h1><button className="primary-button" onClick={clear}>Back to home</button></section> : <>
        <div className="online-room-bar"><span>ROOM <strong>{room.code}</strong></span><span>Round {Math.max(1, room.roundNumber)} · {room.players.length}/4 players</span></div>
        <div className="online-roster">{room.players.map((p) => <div className={`online-player ${p.id === room.currentPlayerId && room.phase === "TURN_INTRO" ? "online-player-active" : ""}`} key={p.id}>
          <strong>{p.displayName}{p.id === room.meId ? " (you)" : ""}</strong><span>{p.isHost ? "Host · " : ""}{!p.connected ? "Reconnecting" : room.phase === "LOBBY" ? p.ready ? "Ready ✓" : "Not ready" : p.recorded ? "Recorded ✓" : room.phase === "LISTEN" ? p.listened ? "Listened ✓" : "Listening" : "Waiting"}</span>
          {me?.isHost && !p.isHost && room.phase === "LOBBY" ? <button className="online-text-button" disabled={busy} onClick={() => void action(() => rooms.remove(member, p.id))}>Remove</button> : null}
        </div>)}</div>
        <section className="screen online-stage">
          {room.phase === "LOBBY" ? <>
            <p className="eyebrow">Bring your people</p><h1>Room <span className="online-code">{room.code}</span></h1>
            <div className="online-invite" aria-label="Invite friends to this room">
              <div className="online-qr">
                <QRCodeSVG value={shareLink} size={200} level="M" marginSize={4}
                  bgColor="#ffffff" fgColor="#000000" role="img"
                  title={`Scan to join SingBack room ${room.code}`} />
              </div>
              <div className="online-invite-details">
                <h2>Scan to join</h2>
                <p>Point your phone camera at this QR code, tap the link, and enter your name. No app needed.</p>
                <div className="online-share"><input aria-label="Room invitation link" value={shareLink} readOnly onFocus={(event) => event.target.select()} />
                  <button className="secondary-button" onClick={() => void navigator.clipboard?.writeText(shareLink).then(() => setCopied(true)).catch(() => setCopied(false))}>{copied ? "Copied!" : "Copy link"}</button></div>
                <p className="online-note">Or open SingBack, choose Join a room, and enter <strong>{room.code}</strong>.</p>
              </div>
            </div>
            <div className="online-actions"><button className={me?.ready ? "secondary-button" : "primary-button"} disabled={busy} onClick={() => void ready()}>{me?.ready ? "Ready ✓ · change" : "Enable mic & ready"}</button>
              {me?.isHost ? <button className="primary-button primary-button-large" disabled={busy || room.players.length < 2 || room.players.some((p) => !p.ready)} onClick={() => void action(() => rooms.action(member, "start"))}>Start mystery song</button> : <p>The host starts once everyone is ready.</p>}</div>
            <p className="online-note">Everyone listens once on their own device, then takes a turn. Stay on this page; refresh reconnects you to the same room.</p>
          </> : null}
          {room.phase === "LISTEN" && room.song ? <>
            <Narrator key={`${room.roundNumber}-listen`} member={member} cue="listen" turnKey={String(room.roundNumber)} />
            <Listen key={`${room.roundNumber}-clip`} song={room.song} done={me?.listened ?? false} busy={busy}
              onDone={() => void action(() => rooms.action(member, "listened"))} />
            {me?.isHost ? <button className="online-text-button" disabled={busy} onClick={() => {
              if (window.confirm("Continue even if someone has not finished listening?")) void action(() => rooms.action(member, "skip"));
            }}>Continue if someone is disconnected</button> : null}
          </> : null}
          {room.phase === "TURN_INTRO" && room.song ? room.currentPlayerId === room.meId ?
            <OnlineRecording key={`${room.roundNumber}-${room.currentPlayerId}`} member={member} song={room.song} onUploaded={(value) => { sequence.current += 1; accept(value); }} /> : <>
              <p className="eyebrow">The stage is theirs</p><h1>{current?.displayName}’s turn</h1><p>{me?.recorded ? "Your take is already being graded in the background." : "Your turn is coming. Keep your microphone ready."}</p>
              <div className="online-waiting-wave" aria-hidden="true">{Array.from({ length: 16 }, (_, i) => <span key={i} style={{ animationDelay: `${i * -80}ms` }} />)}</div>
            </> : null}
          {room.phase === "TURN_INTRO" && me?.isHost ? <button className="online-text-button" disabled={busy} onClick={() => {
            if (window.confirm(`Skip ${current?.displayName}’s turn? This submits a silent take and scores it as missed.`)) void action(() => rooms.action(member, "skip"));
          }}>Skip current player if needed</button> : null}
          {room.phase === "PROCESSING" ? <>
            <p className="eyebrow">The AI judge is listening</p><h1>Building your results</h1>
            <p>{room.progress?.completedPlayers ?? 0} of {room.players.length} performances ready</p>
            <div className="processing-progress" role="progressbar" aria-label="Completed analysis stages" aria-valuemin={0} aria-valuemax={100} aria-valuenow={room.progress?.percent ?? 0}>
              <div className="processing-progress-track"><div className="processing-progress-fill" style={{ width: `${room.progress?.percent ?? 0}%` }} /></div><strong>{room.progress?.percent ?? 0}%</strong></div>
            <ul className="online-progress-list">{room.progress?.players.map((p) => <li key={p.playerId}><span>{p.displayName}</span><span>{({ waiting: "Waiting", queued: "Queued", audio: "Measuring pitch & rhythm", transcription: "Checking lyrics", feedback: "Gemini feedback", complete: "Ready ✓", error: "Retry needed" } as Record<string, string>)[p.stage] ?? p.stage}</span></li>)}</ul>
            <p className="online-note">Real completed stages, not a timer. Results open automatically for everyone.</p>
            {room.error ? <><p role="alert" className="field-error">{room.error}</p>{me?.isHost ? <button className="primary-button" disabled={busy} onClick={() => void action(() => rooms.action(member, "retry"))}>Retry grading</button> : null}</> : null}
          </> : null}
          {room.phase === "RESULTS" && room.results ? <>
            <p className="eyebrow">One room. One crown.</p><h1>{winner?.displayName} takes it!</h1>
            <Narrator key={`${room.roundNumber}-results`} member={member} cue="results" turnKey={String(room.roundNumber)} />
            <p>Play any performance and compare the vocals. No voting or mandatory playback.</p>
            <div className="performance-grid">{room.results.performances.map((p) => <PerformanceCard key={p.revealId} title={p.displayName} mixUrl={p.mixUrl} score={p.score} feedback={p.feedback} detectedLyrics={p.detectedLyrics} evidence={p.evidence} />)}</div>
            {me?.isHost ? <button className="primary-button primary-button-large" disabled={busy} onClick={() => void action(() => rooms.action(member, "rematch"))}>Play again with this room</button> : <p>The host can start another round with the same room.</p>}
          </> : null}
        </section>
      </>}
    </main>
  </div>;
}
