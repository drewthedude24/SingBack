from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from pydantic import BaseModel

from backend.app.config import Settings
from backend.app.models import Feedback, Score

logger = logging.getLogger(__name__)


class GeminiFeedbackPayload(BaseModel):
    summary: str
    strength: str
    improvement: str
    announcer_line: str
    tags: list[str]


def concise(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    prefix = text[: limit - 1]
    return (prefix.rsplit(" ", 1)[0] if " " in prefix else prefix) + "…"


class GeminiFeedbackService:
    """Grounded AI coaching; deterministic scores remain authoritative."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model
        self._timeout_ms = round(settings.external_api_timeout_seconds * 1000)
        self._client = None
        self._client_lock = threading.Lock()

    def prepare(self) -> None:
        if self._api_key:
            self._get_client()

    def _get_client(self):
        from google import genai
        from google.genai import types
        with self._client_lock:
            if self._client is None:
                self._client = genai.Client(api_key=self._api_key,
                    http_options=types.HttpOptions(timeout=self._timeout_ms,
                        retry_options=types.HttpRetryOptions(attempts=1)))
            return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def feedback(
        self,
        *,
        score: Score,
        expected_lyrics: str,
        detected_lyrics: str | None,
        vocal_path: Path,
        reference_vocal_path: Path,
    ) -> Feedback:
        if not self._api_key:
            return self._fallback(score)
        try:
            from google.genai import types

            measurements = {
                "scores": score.model_dump(by_alias=True),
                "expected_lyrics": expected_lyrics,
                "detected_lyrics": detected_lyrics,
            }
            prompt = (
                "You are the SingBack game-show vocal coach. Explain the supplied "
                "deterministic measurements. Compare the attached reference vocal and player "
                "vocal for phrasing, confidence, and delivery. Never create, revise, or "
                "contradict numeric scores. Cite concrete audible evidence, be supportive, "
                "playful, and concise. Keep the summary under 120 characters, strength and "
                "improvement under 100 characters each, announcer line under 140 characters, "
                "and at most three tags. Do not quote more lyrics "
                "than the short phrases already supplied. Measurements:\n"
                + json.dumps(measurements, separators=(",", ":"))
            )
            client = self._get_client()
            response = client.models.generate_content(
                model=self._model,
                contents=[
                    prompt,
                    "Reference vocal:",
                    types.Part.from_bytes(
                        data=reference_vocal_path.read_bytes(), mime_type="audio/wav"
                    ),
                    "Player vocal:",
                    types.Part.from_bytes(
                        data=vocal_path.read_bytes(), mime_type="audio/wav"
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeminiFeedbackPayload,
                    temperature=0.35,
                    # The output limit includes reasoning tokens. With the old
                    # 220-token limit Flash stopped before completing its JSON.
                    max_output_tokens=512,
                    thinking_config=(
                        types.ThinkingConfig(thinking_budget=0)
                        if self._model.startswith("gemini-2.5-flash")
                        else None
                    ),
                ),
            )
            payload = response.parsed
            if not isinstance(payload, GeminiFeedbackPayload):
                payload = GeminiFeedbackPayload.model_validate_json(response.text or "")
            return Feedback(
                summary=concise(payload.summary, 120),
                strength=concise(payload.strength, 100),
                improvement=concise(payload.improvement, 100),
                announcerLine=concise(payload.announcer_line, 140),
                tags=payload.tags[:3],
                source="gemini",
            )
        except Exception as exc:
            logger.warning("Gemini feedback unavailable (%s, status=%s)", type(exc).__name__, getattr(exc, "code", "unknown"))
            return self._fallback(score)

    @staticmethod
    def _fallback(score: Score) -> Feedback:
        available = {
            "pitch": score.pitch,
            "rhythm": score.rhythm,
            "lyrics": score.lyrics,
            "completion": score.completion,
        }
        measured = {name: value for name, value in available.items() if value is not None}
        if not measured:
            return Feedback(
                summary="No reliable vocal measurements were available for this take.",
                strength="The player completed the turn.",
                improvement="Try again closer to the microphone.",
                announcerLine="The mystery singer kept the table guessing.",
                tags=["low confidence"],
                source="fallback",
            )
        strongest = max(measured, key=measured.get)  # type: ignore[arg-type]
        weakest = min(measured, key=measured.get)  # type: ignore[arg-type]
        return Feedback(
            summary=f"A complete memory take with the strongest result in {strongest}.",
            strength=f"{strongest.title()} was the most accurate measured component.",
            improvement=f"Focus on {weakest} during the next round.",
            announcerLine=f"The voice is in, and {strongest} carried this memory remix.",
            tags=[f"strong {strongest}", f"practice {weakest}"],
            source="fallback",
        )
