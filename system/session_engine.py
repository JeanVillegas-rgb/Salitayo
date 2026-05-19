"""
session_engine.py — Word Proficiency flashcard session orchestration.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from groq import Groq
from django.utils import timezone

from .models import (
    WordState,
    SessionLog,
    ActiveSessionState,
    AttemptLog,
    WordProgressionService,
    FeatureExtractor,
)
from .recommender import (
    compose_session,
    propagate_escalation,
    propagate_regression,
)
from .classifier import predict
from .audio_service import AudioService

HEARTS_PER_SESSION = 5


def _stt_language_code(language: str | None) -> str:
    """Map UI language to Whisper ISO-639-1 (Filipino/Tagalog → tl)."""
    if not language:
        return "en"
    key = str(language).lower().strip()
    if key in ("fil", "tl", "filipino", "tagalog"):
        return "tl"
    return "en"


def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s.lower().strip())
    return re.sub(r"[^\w]", "", s, flags=re.UNICODE)


def is_correct(expected: str, transcript: str) -> bool:
    if not transcript:
        return False
    exp = _normalize_text(expected)
    got = _normalize_text(transcript)
    return exp in got or got in exp


def match_accuracy(expected: str, transcript: str) -> float:
    """Pronunciation match score 0–100 (character similarity on normalized text)."""
    exp = _normalize_text(expected)
    got = _normalize_text(transcript)
    if not exp or not got:
        return 0.0
    return round(SequenceMatcher(None, exp, got).ratio() * 100, 1)


def transcribe_audio(
    audio_bytes: bytes,
    api_key: str,
    content_type: str = "audio/webm",
    language: str = "en",
) -> dict:
    lang = _stt_language_code(language)
    if api_key and api_key.startswith("gsk_"):
        client = Groq(api_key=api_key)
        import io
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "attempt.webm"
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file,
            language=lang,
        )
        return {"transcript": (response.text or "").strip(), "confidence": None}
    return AudioService(api_key).transcribe(audio_bytes, content_type, language=lang)


class WordProficiencySession:
    def __init__(self, user_id: int, groq_api_key: str, session_size: int = 10):
        self.user_id = user_id
        self.groq_api_key = groq_api_key
        self.session_size = session_size
        self.state: ActiveSessionState | None = None

    @classmethod
    def resume(cls, user_id: int, groq_api_key: str):
        instance = cls(user_id, groq_api_key)
        instance.state = (
            ActiveSessionState.objects
            .filter(user_id=user_id, is_over=False)
            .first()
        )
        return instance

    def _save(self):
        if self.state:
            self.state.save()

    def _current_word(self):
        if not self.state:
            return None
        wid = self.state.current_word_id
        if not wid:
            return None
        return WordState.objects.filter(id=wid).first()

    def _advance(self):
        self.state.current_index += 1

    def _deduct_heart(self):
        self.state.hearts -= 1

    def start(self, pos_tag: str | None = None, word_ids: list | None = None):
        words = compose_session(
            user_id=self.user_id,
            session_size=self.session_size,
            pos_tag=pos_tag,
            word_ids=word_ids,
        )
        if not words:
            label = pos_tag or "this category"
            return {"error": f"No words available for {label}."}

        last = (
            SessionLog.objects
            .filter(user_id=self.user_id)
            .order_by("-session_number")
            .first()
        )
        session_number = (last.session_number + 1) if last else 1

        log = SessionLog.objects.create(
            user_id=self.user_id,
            session_number=session_number,
            words_presented=[w.word for w in words],
            hearts_remaining=HEARTS_PER_SESSION,
        )

        self.state, _ = ActiveSessionState.objects.update_or_create(
            user_id=self.user_id,
            defaults={
                "session_log":        log,
                "attempt1_word_ids":  [w.id for w in words],
                "attempt2_word_ids":  [],
                "current_attempt":    1,
                "current_index":      0,
                "hearts":             HEARTS_PER_SESSION,
                "attempt1_results":   {},
                "attempt2_results":   {},
                "is_over":            False,
            },
        )

        for ws in words:
            ws.sessions_seen += 1
            ws.last_seen_session = log
            ws.save(update_fields=["sessions_seen", "last_seen_session"])

        return {
            "session_number": session_number,
            "words": [WordProgressionService.word_state_payload(w) for w in words],
            "hearts": HEARTS_PER_SESSION,
            "current_attempt": 1,
        }

    def submit_attempt(
        self,
        audio_bytes: bytes,
        content_type: str = "audio/webm",
        language: str = "en",
    ):
        if not self.state:
            return {"error": "Session not started"}

        word = self._current_word()
        if not word:
            return {"error": "No current word"}

        audio = transcribe_audio(
            audio_bytes, self.groq_api_key, content_type, language=language
        )
        transcript = audio.get("transcript") or ""
        accuracy = match_accuracy(word.word, transcript)
        correct = is_correct(word.word, transcript)

        WordProgressionService.record_outcome(word, correct)

        if not correct:
            self._deduct_heart()

        AttemptLog.objects.create(
            session=self.state.session_log,
            word_state=word,
            attempt_number=self.state.current_attempt,
            correct=correct,
            whisper_transcript=transcript,
            confidence_score=audio.get("confidence"),
            augmentation_level_at_attempt=word.augmentation_level,
            initial_augmentation_level=word.initial_augmentation_level,
            augmentation_gap_at_attempt=word.augmentation_gap,
            severity_at_attempt=word.severity_score,
            feature_vector=FeatureExtractor.from_word_state(word),
        )

        self._store_result(word.id, correct)
        self._advance()
        next_word = self._current_word()

        response = {
            "word":            word.word,
            "correct":         correct,
            "transcript":      transcript,
            "match_accuracy":  accuracy,
            "confidence":      audio.get("confidence"),
            "hearts":          self.state.hearts,
            "hearts_remaining": self.state.hearts,
            "attempt":         self.state.current_attempt,
            "current_word":    WordProgressionService.word_state_payload(word),
        }

        if self._is_attempt_over(next_word):
            return self._handle_attempt_transition(response)

        self._save()
        if next_word:
            response["next_word"] = next_word.word
            response["next_word_state"] = WordProgressionService.word_state_payload(next_word)
        return response

    def _store_result(self, word_id, correct):
        key = str(word_id)
        if self.state.current_attempt == 1:
            data = dict(self.state.attempt1_results)
            data[key] = correct
            self.state.attempt1_results = data
        else:
            data = dict(self.state.attempt2_results)
            data[key] = correct
            self.state.attempt2_results = data

    def _is_attempt_over(self, next_word):
        return self.state.hearts <= 0 or next_word is None

    def _handle_attempt_transition(self, response):
        if self.state.current_attempt == 1:
            failed = [
                int(wid)
                for wid, ok in self.state.attempt1_results.items()
                if not ok
            ]
            if failed:
                self.state.attempt2_word_ids = failed
                self.state.current_attempt = 2
                self.state.current_index = 0
                self.state.hearts = HEARTS_PER_SESSION
                self._save()
                response.update({
                    "attempt_transition": True,
                    "next_word": WordState.objects.get(id=failed[0]).word,
                    "hearts_reset": True,
                })
                nw = WordState.objects.get(id=failed[0])
                response["next_word_state"] = WordProgressionService.word_state_payload(nw)
            else:
                self._save()
                response["session_over"] = True
        else:
            self._save()
            response["session_over"] = True

        return response

    def end(self):
        if not self.state:
            return {"error": "No session"}

        state = self.state
        all_ids = list(set(state.attempt1_word_ids + state.attempt2_word_ids))
        escalated = []
        regressed = []
        propagation_log = []
        rr_applied = []

        words = list(WordState.objects.filter(id__in=all_ids).select_related("features"))

        for ws in words:
            wid = str(ws.id)
            a1 = state.attempt1_results.get(wid)
            a2 = state.attempt2_results.get(wid)

            if a1 is True:
                if WordProgressionService.check_regression(ws):
                    regressed.append(ws)
                    propagation_log += propagate_regression(ws, words)
            elif a1 is False and a2 is True:
                ws.status = "maintained"
                ws.save(update_fields=["status"])
            elif a1 is False:
                WordProgressionService.escalate(ws, bump_level=True)
                escalated.append(ws)
                propagation_log += propagate_escalation(ws, words)

        classifier_results = []
        for ws in words:
            ws.refresh_from_db()
            prediction = predict(ws)
            if WordProgressionService.apply_session_recommendation(ws, prediction):
                rr_applied.append(ws.word)
                ws.refresh_from_db()
            prediction["applied_recommendation"] = ws.word in rr_applied
            prediction["augmentation_level_after"] = ws.augmentation_level
            prediction["aug_tier_label_after"] = ws.aug_tier_label
            classifier_results.append(prediction)

        state.is_over = True
        state.session_log.completed = (state.hearts > 0)
        state.session_log.hearts_remaining = state.hearts
        state.session_log.ended_at = timezone.now()
        state.session_log.save()
        state.save()

        rr_summary = {"under_augmented": 0, "correct": 0, "over_augmented": 0}
        for row in classifier_results:
            label = row.get("gap_label") or ""
            if label == "under_augmented":
                rr_summary["under_augmented"] += 1
            elif label == "over_augmented":
                rr_summary["over_augmented"] += 1
            else:
                rr_summary["correct"] += 1

        return {
            "session_over":           True,
            "completed":              state.session_log.completed,
            "hearts_remaining":       state.hearts,
            "words_attempted":        len(classifier_results),
            "escalated":              [w.word for w in escalated],
            "regressed":              [w.word for w in regressed],
            "classifier_results":     classifier_results,
            "rr_applied":             rr_applied,
            "rr_correction_summary":  rr_summary,
            "propagation":            propagation_log,
        }
