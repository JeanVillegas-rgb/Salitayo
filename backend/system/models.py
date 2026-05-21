from django.db import models
from django.conf import settings


class College(models.Model):
    name = models.CharField(max_length=250)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

class DegreeProgram(models.Model):
    name = models.CharField(max_length=250)
    code = models.CharField(max_length=10, unique=True)
    college = models.ForeignKey(College, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return self.name

class Discipline(models.Model):
    name = models.CharField(max_length=250)
    program = models.ForeignKey(DegreeProgram, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────────────────────────────────────
# WRITING ASSISTANT
# ─────────────────────────────────────────────────────────────────────────────

class Passage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='passages',
    )
    title = models.CharField(max_length=255)
    content = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class WritingSession(models.Model):
    MODE_CHOICES = [
        ('existing_text', 'Existing Text'),
        ('open_topic', 'Open Topic'),
    ]
    LANGUAGE_CHOICES = [
        ('english', 'English'),
        ('filipino', 'Filipino / Tagalog'),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='writing_sessions'
    )
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    language = models.CharField(max_length=20, choices=LANGUAGE_CHOICES, default='english')
    user_text = models.TextField()
    passage = models.ForeignKey(Passage, null=True, blank=True, on_delete=models.SET_NULL)
    identified_topic = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mode} session — {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class FlaggedWord(models.Model):
    TYPE_CHOICES = [
        ('out_of_place', 'Out of Place'),
        ('spelling', 'Spelling'),
        ('grammar', 'Grammar'),
        ('language_mix', 'Language Mix'),
    ]
    SEVERITY_CHOICES = [
        ('gentle', 'Gentle'),
        ('moderate', 'Moderate'),
        ('significant', 'Significant'),
    ]
    session = models.ForeignKey(WritingSession, on_delete=models.CASCADE, related_name='flagged_words')
    original = models.CharField(max_length=255)
    type = models.CharField(max_length=50, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=50, choices=SEVERITY_CHOICES)
    reason = models.TextField()
    applied_suggestion = models.CharField(max_length=255, null=True, blank=True)
    dismissed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.original} ({self.type})"


class FlaggedWordSuggestion(models.Model):
    flagged_word = models.ForeignKey(FlaggedWord, on_delete=models.CASCADE, related_name='suggestions')
    replacement = models.CharField(max_length=255)
    similarity_score = models.IntegerField()

    def __str__(self):
        return f"{self.replacement} ({self.similarity_score}%)"


# ─────────────────────────────────────────────────────────────────────────────
# WORD PROFICIENCY MODULE
# ─────────────────────────────────────────────────────────────────────────────

MAX_AUGMENTATION_LEVEL = 3
AUG_LEVEL_LABELS = {
    0: "plain",
    1: "mild",
    2: "intermediate",
    3: "severe",
}


class WordState(models.Model):

    STATUS = [
        ('regressed',  'REGRESSED'),
        ('maintained', 'MAINTAINED'),
        ('escalated',  'ESCALATED'),
        ('pending',    'PENDING'),
        ('flagged',    'FLAGGED'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    word = models.CharField(max_length=100)

    # Augmentation
    augmentation_level         = models.IntegerField(default=0)
    initial_augmentation_level = models.IntegerField(default=0)  # fixed: was 1
    augmentation_gap           = models.IntegerField(default=0)

    # Escalation
    severity_score     = models.IntegerField(default=0)
    severity_threshold = models.IntegerField(default=3)
    frequency_weight   = models.FloatField(default=1.0)

    # Performance
    total_attempts = models.IntegerField(default=0)
    total_correct  = models.IntegerField(default=0)
    streak_correct = models.IntegerField(default=0)
    streak_miss    = models.IntegerField(default=0)
    attempt_history = models.JSONField(default=list)

    # Session tracking
    sessions_seen                  = models.IntegerField(default=0)
    sessions_since_last_escalation = models.IntegerField(default=0)
    last_seen_session = models.ForeignKey(
        "SessionLog", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="last_seen_words"
    )

    status     = models.CharField(max_length=20, choices=STATUS, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "word")
        ordering = ["-frequency_weight", "-severity_score", "word"]

    def __str__(self):
        return (
            f"{self.user.username} | {self.word} | "
            f"L{self.augmentation_level}({AUG_LEVEL_LABELS[self.augmentation_level]}) | "
            f"gap={self.augmentation_gap:+d} | {self.status}"
        )

    @property
    def accuracy_rate(self):
        if self.total_attempts == 0:
            return 0.0
        return self.total_correct / self.total_attempts

    @property
    def recent_accuracy(self):
        if not self.attempt_history:
            return 0.0
        return sum(self.attempt_history) / len(self.attempt_history)

    @property
    def aug_tier_label(self):
        return AUG_LEVEL_LABELS.get(self.augmentation_level, "plain")


class WordFeatures(models.Model):

    POS_TAGS = [
        ("NOUN", "Noun"), ("VERB", "Verb"), ("ADJ", "Adjective"),
        ("ADV", "Adverb"), ("PRON", "Pronoun"), ("DET", "Determiner"),
        ("ADP", "Adposition"), ("CONJ", "Conjunction"),
        ("NUM", "Numeral"), ("OTHER", "Other"),
    ]

    LANGUAGE_CHOICES = [("en", "English"), ("fil", "Filipino")]

    word_state            = models.OneToOneField("WordState", on_delete=models.CASCADE, related_name="features")
    language              = models.CharField(max_length=8, choices=LANGUAGE_CHOICES, default="en")
    pos_tag               = models.CharField(max_length=10, choices=POS_TAGS, default="OTHER")
    syllable_count        = models.IntegerField(default=1)
    morphological_pattern = models.CharField(max_length=50, blank=True)
    bert_embedding        = models.JSONField(default=list)
    rule_features         = models.JSONField(default=dict)

    def __str__(self):
        return f"Features<{self.word_state.word}>"


class WordProgressionService:
    """
    Stateless service for all WordState mutations.
    Called by views and session_engine — never touches the DB directly
    outside of word_state.save().
    """

    @staticmethod
    def record_outcome(word_state, correct: bool):
        outcome = 1 if correct else 0
        word_state.total_attempts += 1

        history = list(word_state.attempt_history)
        history.append(outcome)
        if len(history) > 7:
            history = history[-7:]
        word_state.attempt_history = history

        if correct:
            word_state.total_correct  += 1
            word_state.streak_correct += 1
            word_state.streak_miss     = 0
        else:
            word_state.streak_miss    += 1
            word_state.streak_correct  = 0

        word_state.augmentation_gap = (
            word_state.augmentation_level - word_state.initial_augmentation_level
        )
        word_state.save()

    @staticmethod
    def _sync_gap(word_state):
        word_state.augmentation_gap = (
            word_state.augmentation_level - word_state.initial_augmentation_level
        )

    @staticmethod
    def _reset_rr_baseline(word_state):
        """New tier is the RR baseline for the next session (gap → 0)."""
        word_state.initial_augmentation_level = word_state.augmentation_level
        word_state.augmentation_gap = 0

    @staticmethod
    def escalate(word_state, *, bump_level: bool = False):
        """
        Record a miss-driven escalation.

        bump_level=True (session end, word not recovered on attempt 2) raises
        augmentation_level immediately so the next session shows stronger RR.
        """
        word_state.severity_score += 1
        word_state.sessions_since_last_escalation = 0
        word_state.frequency_weight = min(3.0, word_state.frequency_weight + 0.5)

        level_bumped = False
        if bump_level or word_state.severity_score >= word_state.severity_threshold:
            if word_state.augmentation_level < MAX_AUGMENTATION_LEVEL:
                word_state.augmentation_level += 1
                level_bumped = True
            word_state.severity_score = 0

        word_state.status = "escalated"
        if bump_level and level_bumped:
            WordProgressionService._reset_rr_baseline(word_state)
        else:
            WordProgressionService._sync_gap(word_state)
        word_state.save()

    @staticmethod
    def check_regression(word_state) -> bool:
        if len(word_state.attempt_history) >= 7 and sum(word_state.attempt_history) >= 5:
            if word_state.augmentation_level > 0:
                word_state.augmentation_level -= 1
            word_state.frequency_weight = max(1.0, word_state.frequency_weight - 0.3)
            word_state.status = "regressed"
            WordProgressionService._reset_rr_baseline(word_state)
            word_state.save()
            return True
        return False

    @staticmethod
    def apply_session_recommendation(word_state, prediction: dict) -> bool:
        """
        Apply classifier RR recommendation (increase / reduce / keep) after a session.

        Updates augmentation_level and resets the RR baseline so the next
        session flashcard reflects the new tier. Works for model and rule_based.
        """
        action = prediction.get("recommendation")
        if action not in ("increase", "reduce"):
            return False

        if action == "increase":
            if word_state.augmentation_level >= MAX_AUGMENTATION_LEVEL:
                return False
            word_state.augmentation_level += 1
            word_state.status = "escalated"
        else:
            if word_state.augmentation_level <= 0:
                return False
            word_state.augmentation_level -= 1
            word_state.status = "regressed"

        word_state.initial_augmentation_level = word_state.augmentation_level
        word_state.augmentation_gap = 0
        word_state.save()
        return True

    @staticmethod
    def apply_rr_correction(word_state, prediction: dict) -> bool:
        """Alias for model-only callers; session end uses apply_session_recommendation."""
        if prediction.get("source") != "model":
            return False
        if word_state.augmentation_gap != 0:
            return False
        return WordProgressionService.apply_session_recommendation(word_state, prediction)

    @staticmethod
    def word_state_payload(word_state) -> dict:
        """JSON-safe snapshot for session start / attempt responses."""
        return {
            "id": word_state.id,
            "word": word_state.word,
            "augmentation_level": word_state.augmentation_level,
            "initial_augmentation_level": word_state.initial_augmentation_level,
            "augmentation_gap": word_state.augmentation_gap,
            "aug_tier_label": word_state.aug_tier_label,
            "status": word_state.status,
        }

    @staticmethod
    def soft_boost(word_state, freq_delta: float = 0.3):
        word_state.frequency_weight = min(3.0, word_state.frequency_weight + freq_delta)
        if word_state.status == "pending":
            word_state.status = "flagged"
        word_state.save()


class FeatureExtractor:
    """
    Builds the flat feature vector used by the classifier.
    Reads from both WordState (progression fields) and WordFeatures (NLP fields).
    """

    POS_MAP = {
        "NOUN": 0, "VERB": 1, "ADJ": 2, "ADV": 3,
        "PRON": 4, "DET": 5, "ADP": 6, "CONJ": 7,
        "NUM": 8, "OTHER": 9,
    }

    @staticmethod
    def from_word_state(word_state) -> dict:
        try:
            features = word_state.features
            pos_encoded    = FeatureExtractor.POS_MAP.get(features.pos_tag, 9)
            syllable_count = features.syllable_count
        except WordFeatures.DoesNotExist:
            pos_encoded    = 9
            syllable_count = 1

        return {
            "augmentation_level":             word_state.augmentation_level,
            "severity_score":                 word_state.severity_score,
            "accuracy_rate":                  word_state.accuracy_rate,
            "recent_accuracy":                word_state.recent_accuracy,
            "total_attempts":                 word_state.total_attempts,
            "streak_correct":                 word_state.streak_correct,
            "streak_miss":                    word_state.streak_miss,
            "sessions_since_last_escalation": word_state.sessions_since_last_escalation,
            "pos_encoded":                    pos_encoded,
            "syllable_count":                 syllable_count,
            "word_length":                    len(word_state.word),
            "frequency_weight":               word_state.frequency_weight,
            "initial_augmentation_level":     word_state.initial_augmentation_level,
            "augmentation_gap":               word_state.augmentation_gap,
        }


# ─────────────────────────────────────────────────────────────────────────────
# SESSION MODELS
# ─────────────────────────────────────────────────────────────────────────────

class SessionLog(models.Model):
    user             = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sessions")
    session_number   = models.IntegerField()
    words_presented  = models.JSONField(default=list)
    hearts_remaining = models.IntegerField(default=5)
    completed        = models.BooleanField(default=False)
    started_at       = models.DateTimeField(auto_now_add=True)
    ended_at         = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.session_number} | {self.user.username} | ❤ {self.hearts_remaining}"


class ActiveSessionState(models.Model):
    """
    Serializable session state — stored in DB so it survives between API calls
    without pickling ORM objects.
    One active session per user at a time.
    """
    user        = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="active_session")
    session_log = models.OneToOneField(SessionLog, on_delete=models.CASCADE, related_name="state")

    attempt1_word_ids = models.JSONField(default=list)   # all session words
    attempt2_word_ids = models.JSONField(default=list)   # failed words from attempt 1

    current_attempt = models.IntegerField(default=1)
    current_index   = models.IntegerField(default=0)
    hearts          = models.IntegerField(default=5)

    attempt1_results = models.JSONField(default=dict)    # {str(word_id): bool}
    attempt2_results = models.JSONField(default=dict)

    is_over    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def current_word_ids(self) -> list:
        return self.attempt1_word_ids if self.current_attempt == 1 else self.attempt2_word_ids

    @property
    def current_word_id(self):
        ids = self.current_word_ids
        return ids[self.current_index] if self.current_index < len(ids) else None

    def __str__(self):
        status = "OVER" if self.is_over else "LIVE"
        return f"ActiveSession | {self.user.username} | Attempt {self.current_attempt} | ❤ {self.hearts} | {status}"


class AttemptLog(models.Model):
    """
    One record per flashcard attempt.
    Snapshot fields preserve state at attempt time for classifier training.

    label (gap-based, 3-class):
        0 → RR over-augmented  (gap < 0)
        1 → RR correct         (gap = 0)
        2 → RR under-augmented (gap > 0)
    """
    session    = models.ForeignKey(SessionLog, on_delete=models.CASCADE, related_name="attempts")
    word_state = models.ForeignKey(WordState,  on_delete=models.CASCADE, related_name="attempt_logs")

    attempt_number = models.IntegerField(default=1)
    correct        = models.BooleanField()

    whisper_transcript            = models.CharField(max_length=200, blank=True)
    confidence_score              = models.FloatField(null=True, blank=True)
    augmentation_level_at_attempt = models.IntegerField(default=0)
    initial_augmentation_level    = models.IntegerField(default=0)
    augmentation_gap_at_attempt   = models.IntegerField(default=0)
    severity_at_attempt           = models.IntegerField(default=0)
    feature_vector                = models.JSONField(default=dict)
    label                         = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        result = "✓" if self.correct else "✗"
        return (
            f"{result} {self.word_state.word} | "
            f"gap={self.augmentation_gap_at_attempt:+d} | "
            f"Attempt {self.attempt_number} | Session {self.session.session_number}"
        )