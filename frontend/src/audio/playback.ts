/**
 * Thin wrapper around a shared AudioContext used to schedule the instrumental
 * during a recording turn. Kept separate from simple reference-clip playback
 * (an <audio> element is sufficient for that) because only the instrumental
 * needs to be scheduled against a precise AudioContext timestamp.
 */
export class InstrumentalPlayer {
  private readonly context: AudioContext;
  private readonly buffers = new Map<string, AudioBuffer>();
  private readonly analyserNode: AnalyserNode;
  private readonly outputGain: GainNode;

  constructor() {
    const globalWindow = window as typeof window & { webkitAudioContext?: typeof AudioContext };
    const AudioContextCtor = globalWindow.AudioContext ?? globalWindow.webkitAudioContext;
    if (!AudioContextCtor) {
      throw new Error("This browser does not support the Web Audio API.");
    }
    this.context = new AudioContextCtor();
    this.analyserNode = this.context.createAnalyser();
    this.analyserNode.fftSize = 1024;
    this.outputGain = this.context.createGain();
    this.outputGain.gain.value = 0.72;
    this.analyserNode.connect(this.outputGain);
    this.outputGain.connect(this.context.destination);
  }

  getAnalyser(): AnalyserNode {
    return this.analyserNode;
  }

  async resume(): Promise<void> {
    if (this.context.state === "suspended") {
      await this.context.resume();
    }
  }

  get currentTime(): number {
    return this.context.currentTime;
  }

  async preload(url: string): Promise<AudioBuffer> {
    const cached = this.buffers.get(url);
    if (cached) return cached;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Could not load instrumental audio (${response.status}).`);
    }
    const arrayBuffer = await response.arrayBuffer();
    const buffer = await this.context.decodeAudioData(arrayBuffer);
    this.buffers.set(url, buffer);
    return buffer;
  }

  /** Schedules playback at an absolute AudioContext time and resolves when it finishes. */
  schedule(buffer: AudioBuffer, whenAudioSec: number): {
    source: AudioBufferSourceNode;
    onEnded: Promise<void>;
  } {
    const source = this.context.createBufferSource();
    source.buffer = buffer;
    source.connect(this.analyserNode);
    const onEnded = new Promise<void>((resolve) => {
      source.addEventListener("ended", () => resolve(), { once: true });
    });
    source.start(whenAudioSec);
    return { source, onEnded };
  }
}
