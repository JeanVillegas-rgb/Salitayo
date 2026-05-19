"""
audio_service.py
----------------
Speech-to-text service (Whisper wrapper)
"""

import io
import math
import openai


class AudioService:
    def __init__(self, openai_api_key: str):
        self.client = openai.OpenAI(api_key=openai_api_key)

    def transcribe(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/webm",
        language: str = "en",
    ) -> dict:
        ext = {
            "audio/webm":  "webm",
            "audio/wav":   "wav",
            "audio/wave":  "wav",
            "audio/x-wav": "wav",
            "audio/mp4":   "mp4",
            "audio/mpeg":  "mp3",
            "audio/ogg":   "ogg",
        }.get(content_type, "webm")

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"attempt.{ext}"

        response = self.client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language or "en",
            response_format="verbose_json",
        )

        transcript = response.text.strip()

        confidence = None
        if hasattr(response, "segments") and response.segments:
            logs = [
                s.get("avg_logprob")
                for s in response.segments
                if s.get("avg_logprob") is not None
            ]
            if logs:
                confidence = math.exp(sum(logs) / len(logs))

        return {
            "transcript": transcript,
            "confidence": round(confidence, 3) if confidence else None,
        }