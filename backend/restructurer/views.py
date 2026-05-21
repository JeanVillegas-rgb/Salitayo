import logging

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework import status
from django.http import HttpResponse

from .serializers import RestructureRequestSerializer
from .services import get_restructurer_service

logger = logging.getLogger(__name__)


def home(request):
        return HttpResponse(
                """
                <html>
                    <head><title>SALITAyo Backend</title></head>
                    <body style="font-family: Arial, sans-serif; padding: 24px; line-height: 1.6;">
                        <h1>SALITAyo Backend is running</h1>
                        <p>Open the frontend at <a href="http://localhost:5173/">http://localhost:5173/</a></p>
                        <p>API endpoint: <code>/api/restructure/</code></p>
                        <p>Use the API response field <code>mode</code> to display whether the local model is active.</p>
                    </body>
                </html>
                """
        )


class RestructureTextView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def post(self, request):
        try:
            serializer = RestructureRequestSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            service = get_restructurer_service()
            input_text = serializer.validated_data["input_text"]
            result = service.restructure(
                text=input_text,
                source_context=serializer.validated_data.get("source_context", ""),
                highlight_words=serializer.validated_data.get("highlight_words", None),
                target_language=serializer.validated_data.get("target_language", "en"),
                metrics=serializer.validated_data.get("metrics", None),
                mixed_output=serializer.validated_data.get("mixed_output", "taglish"),
            )
        except Exception as exc:
            logger.exception("Restructure request failed")
            fallback_text = str(request.data.get("input_text") or "").strip()
            fallback_chunks = []
            if fallback_text:
                fallback_chunks = [
                    {
                        "chunk_id": "chunk-1",
                        "text": fallback_text,
                        "highlight_terms": [],
                        "color_terms": [],
                    }
                ]
            return Response(
                {
                    "success": False,
                    "input_text": fallback_text,
                    "restructured_text": fallback_text,
                    "chunks": fallback_chunks,
                    "mode": "view-error-fallback",
                    "error": str(exc),
                },
                status=status.HTTP_200_OK,
            )

        # The Frontend now handles TTS URL generation dynamically to avoid backend overhead

        return Response(
            {
                "success": True,
                "input_text": input_text,
                **result,
            }
        )

@api_view(["GET"])
def tts_speech(request):
    text = request.query_params.get("text", "")
    lang = request.query_params.get("lang", "en")
    
    if not text:
        return Response({"error": "No text provided"}, status=400)
        
    try:
        service = get_restructurer_service()
        print(f"DEBUG: Neural TTS Request for text: {text[:30]}... (lang: {lang})")
        audio_content = service.generate_groq_audio(text, lang)
    except Exception as exc:
        logger.exception("TTS request failed")
        return Response({"error": f"Failed to generate audio: {exc}"}, status=503)
    
    if audio_content:
        from django.http import HttpResponse
        print("DEBUG: Neural TTS SUCCESS (audio content generated)")
        response = HttpResponse(audio_content, content_type="audio/mpeg")
        # Explicit CORS headers for cross-port stability
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response["Access-Control-Allow-Headers"] = "*"
        return response
    else:
        print("DEBUG: Neural TTS FAILED (returning 500)")
        return Response({"error": "Failed to generate audio"}, status=503)
