from rest_framework import serializers
from .models import Passage


class PassageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passage
        fields = ['id', 'title', 'uploaded_at']


class PassageDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Passage
        fields = ['id', 'title', 'content', 'uploaded_at']


# ── Spelling analysis ────────────────────────────────────────

class AnalyzeRequestSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000)
    target_language = serializers.ChoiceField(
        choices=["auto", "english", "filipino"],
        default="auto",
        required=False,
    )


class ErrorDetailSerializer(serializers.Serializer):
    word = serializers.CharField()
    start = serializers.IntegerField()
    end = serializers.IntegerField()
    error_type = serializers.CharField()
    error_type_label = serializers.CharField()
    error_type_confidence = serializers.FloatField()
    correction = serializers.CharField()
    candidates = serializers.ListField(child=serializers.CharField())
    feedback = serializers.CharField()


class AnalyzeResponseSerializer(serializers.Serializer):
    original_text = serializers.CharField()
    corrected_text = serializers.CharField()
    word_count = serializers.IntegerField()
    error_count = serializers.IntegerField()
    errors = ErrorDetailSerializer(many=True)
    processing_time_ms = serializers.IntegerField()
    language = serializers.CharField(default="english")


# ── Contextual alignment ─────────────────────────────────────

class AlignmentRequestSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000)
    reference_passage = serializers.CharField(min_length=1)


class ContextAlignmentResultSerializer(serializers.Serializer):
    learner_sentence = serializers.CharField()
    reference_sentence = serializers.CharField()
    similarity_score = serializers.FloatField()
    nli_label = serializers.CharField()
    nli_confidence = serializers.FloatField()


class AlignmentResponseSerializer(serializers.Serializer):
    context_alignment_results = ContextAlignmentResultSerializer(many=True)
