from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from backend.app.config import Settings
from backend.app.models import Feedback, Score


class GeminiFeedbackPayload(BaseModel):
    summary: str = Field(max_length=120)
    strength: str = Field(max_length=100)
    improvement: str = Field(max_length=100)
    announcer_line: str = Field(max_length=140)
    tags: list[str] = Field(max_length=3)


class GeminiFeedbackService:
    """Grounded AI coaching; deterministic scores remain authoritative."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.gemini_api_key
        self._model = settings.gemini_model

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
    ) -> Feedback:
        if not self._api_key:
            return self._fallback(score)
        try:
            from google import genai
            from google.genai import types

            measurements = {
                "scores": score.model_dump(by_alias=True),
                "expected_lyrics": expected_lyrics,
                "detected_lyrics": detected_lyrics,
            }
            prompt = (
                "You are the SingBack game-show vocal coach. Explain the supplied "
                "deterministic measurements and briefly consider the attached raw vocal's "
                "energy and delivery. Never create, revise, or contradict numeric scores. "
                "Be specific, supportive, playful, and concise. Do not quote more lyrics "
                "than the short phrases already supplied. Measurements:\n"
                + json.dumps(measurements, separators=(",", ":"))
            )
            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model=self._model,
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=vocal_path.read_bytes(), mime_type="audio/wav"
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=GeminiFeedbackPayload,
                    temperature=0.35,
                    max_output_tokens=220,
                ),
            )
            payload = response.parsed
            if not isinstance(payload, GeminiFeedbackPayload):
                payload = GeminiFeedbackPayload.model_validate_json(response.text or "")
            return Feedback(
                summary=payload.summary,
                strength=payload.strength,
                improvement=payload.improvement,
                announcerLine=payload.announcer_line,
                tags=payload.tags,
                source="gemini",
            )
        except Exception:
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
