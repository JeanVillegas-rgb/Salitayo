"""Word Proficiency API views."""

import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from profiles.views import IsStudent
from .services import (
    import_word_list,
    get_session,
    language_column_ready,
    resume_session,
    run_training,
    sync_user_pos_tags,
)
from .serializers import WordStateSerializer
from .models import ActiveSessionState, WordState


class ImportWordsView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        words = request.data.get("words", [])
        if not words:
            return Response({"error": "No words provided."}, status=400)
        return Response(import_word_list(request.user.id, words), status=201)


class StartSessionView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        session_size = request.data.get("session_size", 10)
        pos_tag = request.data.get("pos_tag") or request.data.get("pos")
        word_ids = request.data.get("word_ids")
        if word_ids is not None and not isinstance(word_ids, list):
            word_ids = None
        if word_ids:
            clean = []
            for i in word_ids:
                try:
                    clean.append(int(i))
                except (TypeError, ValueError):
                    pass
            word_ids = clean or None

        session = get_session(request.user.id, key, session_size=session_size)
        result = session.start(pos_tag=pos_tag, word_ids=word_ids)
        if result.get("error"):
            return Response(result, status=400)
        return Response(result)


class SubmitAttemptView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        audio = request.FILES.get("audio")
        if not audio:
            return Response({"error": "No audio file."}, status=400)
        key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        session = resume_session(request.user.id, key)
        if not session.state:
            return Response({"error": "No active session."}, status=400)
        language = (
            request.data.get("language")
            or request.POST.get("language")
            or "en"
        )
        return Response(
            session.submit_attempt(
                audio.read(), audio.content_type, language=language
            )
        )


class EndSessionView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        session = resume_session(request.user.id, key)
        if not session.state:
            return Response({"error": "No active session."}, status=400)
        return Response(session.end())


class SessionStatusView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        state = ActiveSessionState.objects.filter(
            user=request.user, is_over=False
        ).first()
        if not state:
            return Response({"active": False})
        current_word = None
        wid = state.current_word_id
        if wid:
            ws = WordState.objects.filter(id=wid).first()
            current_word = ws.word if ws else None
        return Response({
            "active": True,
            "current_attempt": state.current_attempt,
            "hearts": state.hearts,
            "current_index": state.current_index,
            "current_word": current_word,
        })


class WordStatusView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        qs = WordState.objects.filter(user=request.user).select_related("features")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        language = request.query_params.get("language")
        if language in ("en", "fil") and language_column_ready():
            qs = qs.filter(features__language=language)
        return Response(WordStateSerializer(qs, many=True).data)


class SyncPosTagsView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        return Response(sync_user_pos_tags(request.user.id))


class WordDetailView(APIView):
    permission_classes = [IsStudent]

    def get(self, request, word):
        try:
            ws = WordState.objects.get(user=request.user, word=word.lower())
        except WordState.DoesNotExist:
            return Response({"error": "Not found."}, status=404)
        return Response(WordStateSerializer(ws).data)


class TrainModelView(APIView):
    permission_classes = [IsStudent]

    def post(self, request):
        return Response(run_training(user_id=request.user.id))


class SessionHistoryView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        from .models import SessionLog
        logs = SessionLog.objects.filter(user=request.user).order_by("-started_at")[:20]
        return Response([
            {
                "session_number": log.session_number,
                "words_presented": log.words_presented,
                "hearts_remaining": log.hearts_remaining,
                "completed": log.completed,
                "started_at": log.started_at,
                "ended_at": log.ended_at,
            }
            for log in logs
        ])
