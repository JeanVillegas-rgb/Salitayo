from rest_framework import serializers
from .models import Passage, WritingSession, FlaggedWord, FlaggedWordSuggestion, WordFeatures, WordProgressionService, WordState, AttemptLog



#WRITING ASSISTANT SERIALIZERS
class PassageSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Passage
        fields = ['id', 'title', 'content', 'uploaded_at']

class PassageListSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Passage
        fields = ['id', 'title', 'uploaded_at']


class FlaggedWordSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model  = FlaggedWordSuggestion
        fields = ['id', 'replacement', 'similarity_score']


class FlaggedWordSerializer(serializers.ModelSerializer):
    suggestions = FlaggedWordSuggestionSerializer(many=True, read_only=True)

    class Meta:
        model  = FlaggedWord
        fields = [
            'id',
            'original',
            'type',
            'severity',
            'reason',
            'applied_suggestion',
            'dismissed',
            'created_at',
            'suggestions',
        ]


class WritingSessionSerializer(serializers.ModelSerializer):
    flagged_words = FlaggedWordSerializer(many=True, read_only=True)
    passage       = PassageListSerializer(read_only=True)

    class Meta:
        model  = WritingSession
        fields = [
            'id',
            'mode',
            'language',
            'user_text',
            'passage',
            'identified_topic',
            'created_at',
            'flagged_words',
        ]




#WORDPROFICIENCYSERIALIZERS

class WordFeaturesSerializer(serializers.ModelSerializer):
    language = serializers.SerializerMethodField()

    def get_language(self, obj):
        return getattr(obj, "language", "en") or "en"

    class Meta:
        model = WordFeatures
        fields = [

            "id",

            "language",

            "pos_tag",

            "syllable_count",

            "morphological_pattern",

            "bert_embedding",

            "rule_features",
        ]

        read_only_fields = [
            "id",
        ]


class WordStateSerializer(serializers.ModelSerializer):
    features = WordFeaturesSerializer(
        read_only=True
    )
    pos_tag = serializers.ReadOnlyField(source="features.pos_tag")
    language = serializers.SerializerMethodField()
    accuracy_rate = serializers.ReadOnlyField()
    recent_accuracy = serializers.ReadOnlyField()
    aug_tier_label = serializers.ReadOnlyField()

    def get_language(self, obj):
        try:
            return getattr(obj.features, "language", "en") or "en"
        except Exception:
            return "en"

    class Meta:

        model = WordState
        fields = [
            "id",
            "word",
            "augmentation_level",
            "initial_augmentation_level",
            "augmentation_gap",
            "severity_score",
            "severity_threshold",
            "frequency_weight",
            "total_attempts",
            "total_correct",
            "streak_correct",
            "streak_miss",
            "attempt_history",
            "sessions_seen",
            "sessions_since_last_escalation",
            "status",
            "pos_tag",
            "language",
            "accuracy_rate",
            "recent_accuracy",
            "aug_tier_label",
            "features",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "augmentation_gap",
            "total_attempts",
            "total_correct",
            "streak_correct",
            "streak_miss",
            "pos_tag",
            "accuracy_rate",
            "recent_accuracy",
            "aug_tier_label",
            "created_at",
            "updated_at",
        ]



class WordStateCreateSerializer(
    serializers.ModelSerializer
):

    # Nested feature payload
    features = serializers.DictField(
        write_only=True
    )
    class Meta:
        model = WordState
        fields = [

            "word",
            "augmentation_level",
            "initial_augmentation_level",
            "severity_threshold",
            "features",
        ]

    def create(self, validated_data):
        feature_data = validated_data.pop(
            "features",
            {}
        )

        user = self.context["request"].user
        word_state = WordState.objects.create(
            user=user,
            **validated_data
        )

        WordFeatures.objects.create(
            word_state=word_state,
            **feature_data
        )

        return word_state
    


class AttemptLogSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = AttemptLog
        fields = [
            "id",
            "word_state",
            "correct",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
        ]