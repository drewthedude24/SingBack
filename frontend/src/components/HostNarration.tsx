import { useEffect, useState } from "react";

import { api, mediaUrl } from "../api/client";
import type { NarrationCue, NarrationResponse } from "../api/types";

interface HostNarrationProps {
  sessionId: string;
  cue: NarrationCue;
}

export function HostNarration({ sessionId, cue }: HostNarrationProps): JSX.Element | null {
  const [narration, setNarration] = useState<NarrationResponse | null>(null);

  useEffect(() => {
    let active = true;
    setNarration(null);
    api
      .narration(sessionId, cue)
      .then((result) => {
        if (active) setNarration(result);
      })
      .catch(() => {
        // Narration is an enhancement; the game remains playable if it is unavailable.
      });
    return () => {
      active = false;
    };
  }, [cue, sessionId]);

  if (!narration) return null;

  return (
    <aside className="host-narration" aria-label="SingBack host narration">
      <div className="host-narration-copy">
        <span className="host-narration-label">
          {narration.source === "elevenlabs" ? "ElevenLabs game host" : "SingBack game host"}
        </span>
        <p>{narration.text}</p>
      </div>
      {narration.audioUrl ? (
        <audio controls autoPlay src={mediaUrl(narration.audioUrl)} aria-label="Play host narration" />
      ) : (
        <span className="narration-fallback">Voice activates when ElevenLabs is configured</span>
      )}
    </aside>
  );
}
