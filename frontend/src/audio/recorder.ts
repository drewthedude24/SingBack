const PREFERRED_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/ogg;codecs=opus",
  "audio/ogg",
];

const EXTENSION_BY_MIME: Record<string, string> = {
  "audio/webm": "webm",
  "audio/ogg": "ogg",
  "audio/wav": "wav",
  "audio/mpeg": "mp3",
  "audio/mp4": "m4a",
};

function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const type of PREFERRED_MIME_TYPES) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

export async function requestMicrophone(): Promise<MediaStream> {
  return navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: false,
      autoGainControl: true,
      channelCount: 1,
    },
  });
}

export function fileFromRecording(blob: Blob, mimeType: string): File {
  const baseType = mimeType.split(";", 1)[0]?.trim() ?? "audio/webm";
  const extension = EXTENSION_BY_MIME[baseType] ?? "webm";
  return new File([blob], `recording.${extension}`, { type: mimeType || baseType });
}

/**
 * Wraps MediaRecorder so callers can await the precise start timestamp
 * (performance.now(), captured on the "start" event) needed for the
 * cross-clock preroll math described in docs/INTEGRATION_CONTRACT.md.
 */
export class TurnRecorder {
  private readonly recorder: MediaRecorder;
  private readonly mimeType: string;
  private readonly chunks: BlobPart[] = [];
  private readonly startedPromise: Promise<number>;
  private resolveStarted!: (value: number) => void;
  private analyserContext: AudioContext | null = null;
  private analyserNode: AnalyserNode | null = null;
  startPerfMs = 0;

  constructor(stream: MediaStream) {
    this.mimeType = pickMimeType();
    this.recorder = this.mimeType
      ? new MediaRecorder(stream, { mimeType: this.mimeType })
      : new MediaRecorder(stream);

    this.startedPromise = new Promise<number>((resolve) => {
      this.resolveStarted = resolve;
    });

    this.recorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    });

    this.recorder.addEventListener("start", () => {
      this.startPerfMs = performance.now();
      this.resolveStarted(this.startPerfMs);
    });

    try {
      const globalWindow = window as typeof window & {
        webkitAudioContext?: typeof AudioContext;
      };
      const AudioContextCtor = globalWindow.AudioContext ?? globalWindow.webkitAudioContext;
      if (AudioContextCtor) {
        this.analyserContext = new AudioContextCtor();
        const source = this.analyserContext.createMediaStreamSource(stream);
        this.analyserNode = this.analyserContext.createAnalyser();
        this.analyserNode.fftSize = 1024;
        source.connect(this.analyserNode);
      }
    } catch {
      this.analyserNode = null;
    }
  }

  getAnalyser(): AnalyserNode | null {
    return this.analyserNode;
  }

  /** Starts capture and resolves with performance.now() at the moment it actually began. */
  start(): Promise<number> {
    this.recorder.start();
    return this.startedPromise;
  }

  stop(): Promise<{ blob: Blob; mimeType: string; durationMs: number }> {
    return new Promise((resolve, reject) => {
      if (this.recorder.state === "inactive") {
        reject(new Error("Recorder already stopped."));
        return;
      }
      this.recorder.addEventListener(
        "stop",
        () => {
          const stopPerfMs = performance.now();
          const type = this.recorder.mimeType || this.mimeType || "audio/webm";
          void this.analyserContext?.close();
          resolve({
            blob: new Blob(this.chunks, { type }),
            mimeType: type,
            durationMs: Math.max(1, Math.round(stopPerfMs - this.startPerfMs)),
          });
        },
        { once: true },
      );
      this.recorder.stop();
    });
  }
}
