# Word Proficiency Module — README

> **Defense prep reference** — covers architecture, data flow, and key code blocks for every file in the Word Proficiency module.

---

## Table of Contents

1. [What This Module Does](#what-this-module-does)
2. [Architecture Overview](#architecture-overview)
3. [Data Flow: A Full Session](#data-flow-a-full-session)
4. [File-by-File Breakdown](#file-by-file-breakdown)
   - [models.py](#modelspy)
   - [services.py](#servicespy)
   - [session_engine.py](#session_enginepy)
   - [recommender.py](#recommenderpy)
   - [classifier.py](#classifierpy)
   - [bert_tagger.py](#bert_taggerpy)
   - [audio_service.py](#audio_servicepy)
   - [seed_vocabulary.py](#seed_vocabularypy)
   - [serializers.py](#serializerspy)
   - [views_wp.py](#views_wppy)
   - [urls.py](#urlspy)
5. [The NLP Contribution Explained](#the-nlp-contribution-explained)
6. [Key Design Decisions](#key-design-decisions)

---

## What This Module Does

The Word Proficiency module is a **speech-based vocabulary training system**. Students are shown words, speak them aloud, and the system:

1. **Transcribes** their speech using Whisper (via Groq or OpenAI)
2. **Evaluates** pronunciation correctness
3. **Tracks** word-level performance over time (streaks, accuracy, augmentation level)
4. **Recommends** the next session's word list based on difficulty and history
5. **Trains an ML classifier** (Logistic Regression + BERT) to detect when the system's own difficulty assignments were wrong — and corrects them

---

## Architecture Overview

```
Request
  │
  ▼
views_wp.py          ← REST API layer (DRF APIViews)
  │
  ▼
services.py          ← Orchestration / entry point functions
  │
  ├── session_engine.py   ← Flashcard session state machine
  │       ├── audio_service.py   ← Whisper STT
  │       ├── recommender.py     ← Word selection scoring
  │       └── classifier.py     ← ML inference at session end
  │
  ├── bert_tagger.py      ← POS tagging + BERT embeddings
  └── models.py           ← Django ORM models + business logic
```

---

## Data Flow: A Full Session

```
POST /session/start/
  → services.get_session()
  → session_engine.WordProficiencySession.start()
  → recommender.compose_session()         ← picks words by score
  → creates SessionLog + ActiveSessionState in DB
  → returns word list to frontend

POST /session/attempt/  (repeated per word)
  → session_engine.submit_attempt()
  → audio_service.transcribe()            ← Whisper STT
  → is_correct() / match_accuracy()       ← pronunciation check
  → WordProgressionService.record_outcome() ← updates streaks/history
  → AttemptLog saved to DB
  → returns result + next word

POST /session/end/
  → session_engine.end()
  → WordProgressionService.escalate/regress per word
  → recommender.propagate_escalation/regression ← affects similar words
  → classifier.predict() per word         ← ML correction pass
  → WordProgressionService.apply_session_recommendation()
  → returns full summary
```

---

## File-by-File Breakdown

---

### models.py

**What it contains:** All Django database models and the core business logic services.

#### Key Models

| Model | Purpose |
|---|---|
| `WordState` | Per-user per-word difficulty tracker |
| `WordFeatures` | Linguistic metadata (POS, syllables, BERT embedding) |
| `SessionLog` | Record of each training session |
| `ActiveSessionState` | Live session state (current word, hearts, attempt index) |
| `AttemptLog` | Individual pronunciation attempt record |

#### Important Block: `WordProgressionService`

This is the **core business logic** class. Three key methods:

```python
# 1. Records a correct/incorrect attempt → updates streaks and history
WordProgressionService.record_outcome(word_state, correct: bool)

# 2. Escalates difficulty when a word is consistently missed
WordProgressionService.escalate(word_state, bump_level=True)

# 3. Checks if a mastered word should drop in difficulty
WordProgressionService.check_regression(word_state) → bool
```

#### Important Block: `augmentation_gap`

```python
# augmentation_gap = current level - initial level (set by Reading Restructurer)
# gap < 0  → RR over-augmented (system was too hard on the student)
# gap = 0  → RR was correct
# gap > 0  → RR under-augmented (system was too easy)
```

This gap is what the ML classifier learns to predict and correct.

#### Important Block: `FeatureExtractor.from_word_state()`

Converts a `WordState` ORM object into a flat dictionary of numeric features for the classifier:

```python
fv = FeatureExtractor.from_word_state(ws)
# Returns: {"augmentation_level": 2, "severity_score": 0.7, "accuracy_rate": 0.6, ...}
```

---

### services.py

**What it contains:** Entry-point functions that the views call. Thin orchestration layer — no business logic lives here.

#### Important Block: `import_word_list()`

```python
def import_word_list(user_id: int, words: list) -> dict:
```

For each word in the input list:
1. Skips if already exists for this user
2. Calls `analyze_word()` to get POS tag, syllable count, BERT embedding
3. Creates `WordState` + `WordFeatures` records
4. Sets `augmentation_level = initial_augmentation_level = rr_level` (gap starts at 0)

#### Important Block: `retag_user_words()`

Re-runs POS tagging for all of a user's words, optionally applying seed vocabulary overrides. Safe to call multiple times (idempotent). Used by the `SyncPosTagsView`.

#### Important Block: `language_column_ready()`

A **migration guard** — checks whether the `language` column exists on `WordFeatures` before trying to use it. Prevents crashes during phased deployments:

```python
def language_column_ready() -> bool:
    # Inspects DB schema at runtime to check if migration 0004 has run
```

---

### session_engine.py

**What it contains:** The `WordProficiencySession` class — the stateful session machine.

#### Important Block: `WordProficiencySession` class structure

```python
session = WordProficiencySession(user_id, groq_api_key, session_size=10)
session.start()          # picks words, creates DB state
session.submit_attempt() # processes one audio attempt
session.end()            # finalizes, runs ML, returns summary
```

`resume()` is a classmethod that reloads an in-progress session from `ActiveSessionState`:

```python
session = WordProficiencySession.resume(user_id, groq_api_key)
# → loads existing ActiveSessionState from DB, no new session created
```

#### Important Block: `submit_attempt()`

The most important method in the module:

```python
def submit_attempt(self, audio_bytes, content_type, language):
    word = self._current_word()
    audio = transcribe_audio(audio_bytes, self.groq_api_key, ...)  # STT
    correct = is_correct(word.word, transcript)                     # match check
    WordProgressionService.record_outcome(word, correct)            # update stats
    if not correct:
        self._deduct_heart()                                        # lose a heart
    AttemptLog.objects.create(...)                                  # save to DB
    self._advance()                                                 # move to next word
```

#### Important Block: Two-Attempt System

```python
# After attempt 1: words the student got WRONG go into attempt2_word_ids
# Attempt 2 is a second-chance round for failed words only
# Hearts reset between attempts
if self.state.current_attempt == 1:
    failed = [wid for wid, ok in self.state.attempt1_results.items() if not ok]
    self.state.attempt2_word_ids = failed
    self.state.current_attempt = 2
    self.state.hearts = HEARTS_PER_SESSION
```

#### Important Block: `is_correct()` and `match_accuracy()`

```python
def is_correct(expected, transcript) -> bool:
    # Normalized substring match — "mountain" in "the mountain" → True
    exp = _normalize_text(expected)
    got = _normalize_text(transcript)
    return exp in got or got in exp

def match_accuracy(expected, transcript) -> float:
    # SequenceMatcher ratio × 100 — gives a 0–100 pronunciation score
    return round(SequenceMatcher(None, exp, got).ratio() * 100, 1)
```

#### Important Block: `end()` — ML correction pass

At session end, the classifier runs on every word and may adjust augmentation levels:

```python
for ws in words:
    prediction = predict(ws)                                    # ML inference
    if WordProgressionService.apply_session_recommendation(ws, prediction):
        rr_applied.append(ws.word)                             # gap corrected
```

---

### recommender.py

**What it contains:** Word selection scoring and difficulty propagation.

#### Important Block: `_score()` — priority scoring

Each word gets a priority score for session inclusion:

```python
def _score(ws: WordState) -> float:
    score = (
        ws.frequency_weight     * 3.0   # how urgently this word needs practice
        + ws.severity_score     * 2.0   # how bad performance has been
        + ws.augmentation_level * 1.5   # harder words get slight priority
        + ws.streak_miss        * 1.0   # recent miss streak
    )
    if ws.total_attempts == 0:
        score += 2.0   # bonus for never-seen words
    if is_mastered:
        score -= 4.0   # penalty to deprioritize mastered words
    return score
```

#### Important Block: `propagate_escalation()`

When one word gets harder, **similar words get pre-escalated** too (same POS tag, similar syllable count). This is the **difficulty contagion** mechanism:

```python
def propagate_escalation(source_ws, context_words):
    for cf in context_words:
        if same POS and similar syllable count:
            cf.augmentation_level += 1   # pre-escalate
```

---

### classifier.py

**What it contains:** The NLP/ML layer — feature engineering, training, and inference.

#### Important Block: Feature Matrix

The model uses two feature types combined:

```
Columns [0..13]   → 14 tabular features (accuracy, streaks, augmentation gap, etc.)
Columns [14..781] → 768-dim BERT embedding (PCA reduced to 16 dims)
```

```python
X = np.hstack([tabular_features, pca_reduced_bert_embedding])
```

The BERT embedding is the **NLP contribution** — it captures semantic/phonological word properties that tabular features can't express.

#### Important Block: Gap-Based Labels

The classifier does **not** predict whether a student will pass or fail. It predicts whether the Reading Restructurer's original difficulty assignment was correct:

```python
def build_labels(word_states):
    # gap = augmentation_level - initial_augmentation_level
    if gap < 0:  → label 0 (over_augmented — RR was too hard)
    if gap == 0: → label 1 (correct — RR nailed it)
    if gap > 0:  → label 2 (under_augmented — RR was too easy)
```

This makes the model learn to **correct** the Reading Restructurer, not replicate it.

#### Important Block: `train()`

```python
def train(user_id=None, min_samples=20):
    # 1. Load WordState records with enough attempts
    # 2. Build feature matrix (tabular + BERT)
    # 3. PCA: reduce 768 → 16 dimensions
    # 4. LogisticRegression (multinomial, class_weight="balanced")
    # 5. Save pipeline + PCA to classifier.joblib
```

Uses `class_weight="balanced"` because the "correct" class (gap=0) will dominate — this prevents the model from just always predicting "correct."

#### Important Block: `predict()` fallback

If no trained model exists yet, the classifier falls back to **rule-based inference** using the gap directly:

```python
if saved is None:
    gap = word_state.augmentation_gap
    cls = 0 if gap < 0 else (1 if gap == 0 else 2)
    return {..., "source": "rule_based"}
```

---

### bert_tagger.py

**What it contains:** POS tagging (via spaCy) and BERT embedding extraction.

#### Important Block: `tag_word()`

Uses spaCy to tag a word in context (placed in a carrier sentence for better accuracy):

```python
doc = nlp(f"I often think about {word}.")
# → tags the word in a real sentence context, not in isolation
```

Maps spaCy's fine-grained POS tags to the app's coarser set (`NOUN`, `VERB`, `ADJ`, etc.).

#### Important Block: `get_embedding()`

Loads `bert-base-multilingual-cased` and extracts the word's embedding:

```python
# Tokenizes the word → runs through BERT → averages token embeddings
tokens = outputs.last_hidden_state[0][1:-1]  # strips [CLS] and [SEP]
return tokens.mean(dim=0).tolist()           # 768-dim vector
```

Multilingual BERT is used because the vocabulary includes both **English and Filipino** words.

#### Important Block: `count_syllables()`

Lightweight regex-based syllable counter (used when BERT/spaCy are unavailable):

```python
# Strips trailing 'e', counts vowel clusters
w = re.sub(r"e$", "", word.lower())
# Counts transitions into vowel groups → each = 1 syllable
```

---

### audio_service.py

**What it contains:** A wrapper around OpenAI's Whisper API for speech-to-text.

#### Important Block: `transcribe()`

```python
def transcribe(self, audio_bytes, content_type, language):
    # 1. Maps MIME type → file extension (webm, wav, mp4, etc.)
    # 2. Wraps bytes in BytesIO with correct .name extension (Whisper needs this)
    # 3. Calls whisper-1 with verbose_json to get segments
    # 4. Computes confidence from avg_logprob of segments:
    confidence = math.exp(sum(avg_logprobs) / len(avg_logprobs))
    # log-probability → probability via exp()
```

**Note:** In `session_engine.py`, Groq's `whisper-large-v3` is tried first (faster/cheaper). This class handles the OpenAI fallback.

---

### seed_vocabulary.py

**What it contains:** Hardcoded word lists for English and Filipino, used to seed the database.

#### Important Block: `SEED_VOCABULARY`

3 words per POS tag × 10 POS tags × 2 languages = **60 seed words**. Each has a preset `rr_augmentation_level` (0, 1, or 2) cycling through difficulties.

#### Important Block: `build_seed_entries(locale)`

Flattens the nested dict into a list of dicts ready for `import_word_list()`:

```python
{"word": "mountain", "pos_tag": "NOUN", "language": "en", "rr_augmentation_level": 0}
```

#### Important Block: `get_seed_overrides()`

Returns a `word → {pos_tag, language}` lookup used by `retag_user_words()` to ensure seed words always get the correct POS tags, overriding whatever spaCy might guess.

---

### serializers.py

**What it contains:** DRF serializers for the Word Proficiency models.

#### Key serializers

| Serializer | Used for |
|---|---|
| `WordStateSerializer` | Reading word state (GET responses) |
| `WordStateCreateSerializer` | Creating a word with nested features (POST) |
| `AttemptLogSerializer` | Attempt records |
| `WordFeaturesSerializer` | Linguistic metadata |

#### Important Block: Read-only computed fields

Several fields on `WordStateSerializer` are computed properties on the model, exposed as read-only:

```python
accuracy_rate    = serializers.ReadOnlyField()   # total_correct / total_attempts
recent_accuracy  = serializers.ReadOnlyField()   # accuracy over last N attempts
aug_tier_label   = serializers.ReadOnlyField()   # "None" / "Mild" / "Moderate" / "Strong"
```

#### Important Block: `WordStateCreateSerializer.create()`

Handles nested creation — the `features` dict is popped from validated data and used to create a `WordFeatures` record linked to the new `WordState`:

```python
feature_data = validated_data.pop("features", {})
word_state = WordState.objects.create(user=user, **validated_data)
WordFeatures.objects.create(word_state=word_state, **feature_data)
```

---

### views_wp.py

**What it contains:** DRF `APIView` classes — the HTTP interface to the module.

All views use `permission_classes = [IsStudent]`.

#### Endpoint → View mapping

| View | Method | What it does |
|---|---|---|
| `ImportWordsView` | POST | Calls `import_word_list()` |
| `StartSessionView` | POST | Creates session, returns word list |
| `SubmitAttemptView` | POST | Processes one audio file |
| `EndSessionView` | POST | Finalizes session, runs ML |
| `SessionStatusView` | GET | Returns current session state |
| `WordStatusView` | GET | Lists all user's words + states |
| `WordDetailView` | GET | Single word detail |
| `SyncPosTagsView` | POST | Reruns POS tagging |
| `TrainModelView` | POST | Triggers classifier training |
| `SessionHistoryView` | GET | Last 20 session logs |

#### Important Block: API key resolution

The system supports both Groq and OpenAI backends transparently:

```python
key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
# Groq keys start with "gsk_" → session_engine routes to Groq Whisper
# Otherwise → routes to OpenAI Whisper via audio_service.py
```

#### Important Block: `SubmitAttemptView`

Audio is received as a multipart file upload, not JSON:

```python
audio = request.FILES.get("audio")        # multipart/form-data
language = request.data.get("language") or request.POST.get("language") or "en"
# language checked in both data and POST to handle different client encodings
session.submit_attempt(audio.read(), audio.content_type, language=language)
```

---

### urls.py

**What it contains:** URL routing for all 10 endpoints.

```
words/import/         → ImportWordsView
words/                → WordStatusView
words/sync-pos/       → SyncPosTagsView
words/<str:word>/     → WordDetailView
session/start/        → StartSessionView
session/attempt/      → SubmitAttemptView
session/end/          → EndSessionView
session/status/       → SessionStatusView
session/history/      → SessionHistoryView
train/                → TrainModelView
```

**Note:** `words/sync-pos/` must be listed **before** `words/<str:word>/` to avoid `sync-pos` being caught as a word string.

---

## The NLP Contribution Explained

This is likely what your panel will focus on. Here is the clean explanation:

**The problem:** The Reading Restructurer (RR) assigns each word an initial difficulty level (`rr_augmentation_level`). But it can be wrong — it might be too hard or too easy for a specific student.

**The contribution:** A logistic regression classifier trained on BERT embeddings + behavioral features learns to detect *when* the RR was wrong and in *which direction*, then corrects the augmentation level automatically.

**Why BERT:** Raw word features (syllable count, POS tag) are insufficient — semantically similar words behave similarly in practice. BERT's 768-dimensional multilingual embeddings capture this word-level similarity across English and Filipino. PCA reduces these to 16 dimensions to avoid the curse of dimensionality on small datasets.

**The label (gap):** Rather than predicting performance, the model predicts the *gap* between the RR's initial decision and where the word ended up after real session behavior. This means it's learning to correct the upstream system — which is the genuine NLP contribution.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Gap-based labels (not binary pass/fail) | Makes the classifier correct the RR rather than replicate student behavior |
| Multinomial logistic regression (not deep learning) | Interpretable, works on small datasets, fast to retrain |
| Rule-based fallback in `predict()` | System works end-to-end before any model is trained |
| `bert-base-multilingual-cased` | Single model handles both English and Filipino |
| PCA 768→16 | Prevents overfitting on small word lists; preserves ~variance |
| `class_weight="balanced"` | Gap=0 ("correct") dominates naturally; balanced weights prevent trivial classifier |
| Two-attempt session structure | Failed words get a second chance; data from both attempts logged separately |
| `propagate_escalation/regression` | Difficulty changes on one word generalize to similar words in the same session |
