import os
import fitz
from docx import Document

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Passage
from .serializers import (
    AnalyzeRequestSerializer,
    AnalyzeResponseSerializer,
    AlignmentRequestSerializer,
    AlignmentResponseSerializer,
    PassageSerializer,
    PassageDetailSerializer,
)
from .services.pipeline import analyze
from .services.alignment_pipeline import run_alignment


def _classify_input(text: str, target_language: str) -> str:
    """
    Returns one of: 'english' | 'filipino' | 'taglish_to_english' | 'taglish_to_filipino'

    When target_language is explicitly 'english' or 'filipino', langdetect is
    skipped — the user already knows their text has mixed content.
    Auto mode uses langdetect to decide.
    """
    from django.conf import settings
    if not getattr(settings, "GROQ_API_KEY", ""):
        return "english"

    # Explicit selection: trust the user, route directly to Groq
    if target_language == "english":
        return "taglish_to_english"
    if target_language == "filipino":
        return "taglish_to_filipino"

    # Auto mode: use langdetect
    try:
        from langdetect import detect_langs
        langs = detect_langs(text)
        lang_dict = {l.lang: l.prob for l in langs}
        has_english  = lang_dict.get("en", 0) > 0.15
        has_filipino = lang_dict.get("tl", 0) > 0.15
        is_taglish   = has_english and has_filipino
        dominant     = max(lang_dict, key=lang_dict.get)
    except Exception:
        is_taglish = False
        dominant   = "en"

    if is_taglish:
        return "taglish_to_filipino"

    return "filipino" if dominant == "tl" else "english"


class AnalyzeView(APIView):
    def post(self, request):
        req_ser = AnalyzeRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return Response(req_ser.errors, status=status.HTTP_400_BAD_REQUEST)

        text            = req_ser.validated_data["text"]
        target_language = req_ser.validated_data.get("target_language", "auto")
        route           = _classify_input(text, target_language)

        if route == "filipino":
            from .services.filipino_pipeline import analyze_filipino
            result = analyze_filipino(text)
        elif route == "taglish_to_filipino":
            from .services.filipino_pipeline import analyze_taglish_to_filipino
            result = analyze_taglish_to_filipino(text)
        elif route == "taglish_to_english":
            from .services.filipino_pipeline import analyze_taglish_to_english
            result = analyze_taglish_to_english(text)
        else:
            result = analyze(text)
            result["language"] = "english"

        res_ser = AnalyzeResponseSerializer(result)
        return Response(res_ser.data, status=status.HTTP_200_OK)


class AlignmentView(APIView):
    def post(self, request):
        req_ser = AlignmentRequestSerializer(data=request.data)
        if not req_ser.is_valid():
            return Response(req_ser.errors, status=status.HTTP_400_BAD_REQUEST)

        results = run_alignment(
            req_ser.validated_data["text"],
            req_ser.validated_data["reference_passage"],
        )
        res_ser = AlignmentResponseSerializer({"context_alignment_results": results})
        return Response(res_ser.data, status=status.HTTP_200_OK)


class HealthView(APIView):
    def get(self, request):
        return Response({"status": "ok"})


class PassageListView(APIView):
    def get(self, request):
        passages = Passage.objects.all().order_by('-uploaded_at')
        serializer = PassageSerializer(passages, many=True)
        return Response({"passages": serializer.data})


class PassageDetailView(APIView):
    def get(self, request, passage_id):
        try:
            passage = Passage.objects.get(id=passage_id)
            serializer = PassageDetailSerializer(passage)
            return Response(serializer.data)
        except Passage.DoesNotExist:
            return Response({"error": "Passage not found."}, status=status.HTTP_404_NOT_FOUND)


class PassageExtractView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get('file')
        title = request.data.get('title', '').strip()

        if not file:
            return Response({"error": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

        filename = file.name.lower()
        title = title or file.name

        try:
            if filename.endswith('.pdf'):
                doc = fitz.open(stream=file.read(), filetype="pdf")
                text = "".join(page.get_text() for page in doc)

            elif filename.endswith('.docx'):
                doc = Document(file)
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())

            else:
                return Response(
                    {"error": "Only PDF and DOCX files are supported."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if not text.strip():
                return Response(
                    {"error": "Could not extract any text from the file."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            words = text.split()
            truncated = len(words) > 3000
            if truncated:
                text = " ".join(words[:3000])

            passage = Passage.objects.create(title=title, content=text.strip())

            return Response({
                "id": passage.id,
                "title": passage.title,
                "truncated": truncated,
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": f"Could not read this file: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PassageDeleteView(APIView):
    def delete(self, request, passage_id):
        try:
            passage = Passage.objects.get(id=passage_id)
            passage.delete()
            return Response({"status": "deleted"})
        except Passage.DoesNotExist:
            return Response({"error": "Passage not found."}, status=status.HTTP_404_NOT_FOUND)
