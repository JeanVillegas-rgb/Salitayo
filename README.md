# SALITAyo — Assistive Writing Coach for Dyslexic Learners

> **SALITAyo** (Filipino: "our word / our speech") is a web-based writing assistance tool designed to support learners with dyslexia. It detects and classifies spelling errors, generates targeted corrections, and checks whether the learner's writing is semantically aligned with a reference passage — all within a single integrated interface.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Full Data Flow](#3-full-data-flow)
4. [NLP Components](#4-nlp-components)
   - [T5-small Reranker](#41-t5-small-reranker)
   - [RandomForest Error Classifier](#42-randomforest-error-classifier)
   - [DeBERTa-v2 NLI Aligner](#43-deberta-v2-nli-aligner)
5. [RAG-Based Contextual Alignment](#5-rag-based-contextual-alignment)
6. [Candidate Generation Pipeline](#6-candidate-generation-pipeline)
7. [Setup and Installation](#7-setup-and-installation)
8. [Known Limitations](#8-known-limitations)
9. [Datasets and Citations](#9-datasets-and-citations)

---

## 1. Project Overview

### Who it is for

SALITAyo is designed for educators and learners in contexts where dyslexia is a factor in reading and writing difficulties. The primary user is a learner who types or pastes a short passage of writing and receives:

- a list of suspected spelling errors colour-coded by **error type** (not just "wrong word"),
- a specific correction for each error backed by a trained reranker,
- a plain-language explanation of *why* each word is likely wrong (e.g. "You swapped two adjacent letters"),
- an optional **contextual alignment** report comparing the learner's sentences against a teacher-uploaded reference passage.

### Research gaps addressed

| Gap | Description | Component |
|-----|-------------|-----------|
| **Gap 1** | Existing spell-checkers identify *that* a word is wrong but not *how* it is wrong. Dyslexia research identifies five distinct error types: phonetic substitution, letter reversal, letter omission, letter insertion, and letter transposition. Classifying these allows targeted pedagogical feedback. | `error_classifier_service.py` |
| **Gap 2** | Dictionary-based candidate generators (SymSpell) rank candidates by edit distance and word frequency, but phonetic misspellings like *wuz* and *becuz* are too far from the correct spelling in character-edit space. A trained seq2seq reranker is needed to select among candidates using learned spelling correction patterns. | `reranker_service.py` |
| **Gap 5** | Spell-checkers have no awareness of whether a corrected sentence is contextually appropriate relative to a given source text. Natural Language Inference (NLI) can check whether a learner's sentence *entails*, *contradicts*, or is *neutral* with respect to a reference — a signal that guides comprehension, not just orthography. | `nli_aligner_service.py` |
| **Gap 6** | Existing tools address spelling, grammar, or comprehension in isolation. SALITAyo integrates error detection, classification, reranking, and contextual alignment into a single environment so a learner never leaves the interface. | `App.jsx` + Django REST API |

### Tech stack and justification

| Technology | Role | Why |
|---|---|---|
| **Django 6.0.5** + Django REST Framework | Backend API server | Mature Python web framework; DRF provides serialization, validation, and JSON responses with minimal boilerplate. `AppConfig.ready()` enables reliable model pre-loading at startup. |
| **React 19** + Vite 8 | Frontend SPA | React's component model isolates per-error UI state (applied/undo per card); Vite's dev-server proxy eliminates CORS complexity during development. |
| **SymSpell** (Garbe, 2018) | Candidate generation | Sub-millisecond lookup with pre-computed delete combinations; supports parameterised edit distance ceilings, which this system uses to run two instances (tight max_ed=2 and wide max_ed=4) in a single pipeline. |
| **T5-small** | Spelling reranker | Seq2seq architecture learns the conditional distribution P(correct \| misspelled, candidates) from the Birkbeck + TOEFL-Spell corpora; small model size (~60 MB) keeps inference latency acceptable on CPU. |
| **scikit-learn RandomForest** | Error type classifier | Interpretable, fast inference, no GPU required. Achieves weighted F1=0.981 on the Birkbeck corpus after a 17-feature engineering pass that captures edit-distance, phonetic, positional, and n-gram signals. |
| **DeBERTa-v2** | NLI contextual aligner | DeBERTa's disentangled attention and enhanced mask decoder outperform BERT-family models on NLI benchmarks (He et al., 2021). Fine-tuned on a 4-class schema (entailment / contradiction / neutral / off_topic) derived from MultiNLI + SNLI. |
| **paraphrase-MiniLM-L3-v2** | RAG sentence retrieval | Lightweight (17 MB) sentence encoder; cosine similarity between L2-normalised embeddings is a reliable proxy for semantic relatedness at the sentence level. Used only for retrieval, not for classification. |
| **spaCy en_core_web_sm** | Sentence segmentation | Reliable rule-based + statistical sentence boundary detection needed before RAG and NLI can operate at the sentence level. |
| **SQLite** | Reference passage storage | Self-contained; no external database process needed for local deployment. Passages are extracted from PDF/DOCX and stored as plain text. |

---

## 2. System Architecture

### Folder structure

```
SALITAyo/
├── backend/
│   ├── salitayo/
│   │   ├── settings.py              # Django config, TRAINED_MODELS_DIR, LOGGING
│   │   ├── urls.py                  # Root URL — mounts /api/ prefix
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   ├── assistive_writing_coach/
│   │   ├── apps.py                  # AppConfig.ready() — pre-loads all models at startup
│   │   ├── models.py                # Passage model (id, title, content, uploaded_at)
│   │   ├── serializers.py           # DRF serializers for all request/response shapes
│   │   ├── views.py                 # AnalyzeView, AlignmentView, Passage CRUD views
│   │   ├── urls.py                  # /analyze/, /alignment/, /passages/, /health/
│   │   │
│   │   └── services/
│   │       ├── pipeline.py                 # Main spelling analysis pipeline
│   │       ├── candidate_generator.py      # SymSpell tight + wide + Wikipedia lookup
│   │       ├── reranker_service.py         # T5-small seq2seq reranker
│   │       ├── error_classifier_service.py # RandomForest error type classifier
│   │       ├── feature_extractor.py        # 17-feature vector for classifier
│   │       ├── alignment_pipeline.py       # Sentence-level RAG + NLI pipeline
│   │       ├── retrieval_service.py        # MiniLM cosine similarity retrieval
│   │       └── nli_aligner_service.py      # DeBERTa-v2 NLI inference
│   │
│   ├── trained_models/
│   │   ├── reranker/
│   │   │   └── final_model/         # T5-small fine-tuned (model.safetensors + tokenizer)
│   │   ├── error_classifier/
│   │   │   ├── error_classifier.joblib   # Serialised RandomForest
│   │   │   └── training_metadata.json    # F1, CV scores, feature names, data sources
│   │   └── nli_model/
│   │       └── final_model/         # DeBERTa-v2 fine-tuned (model.safetensors + tokenizer)
│   │
│   ├── data/
│   │   └── wikipedia_misspellings.txt   # 4,310 misspelling→correction pairs
│   │
│   ├── db.sqlite3                   # SQLite database (auto-created on migrate)
│   └── manage.py
│
└── frontend/
    ├── src/
    │   ├── App.jsx                  # Main writing coach interface (all core UI)
    │   ├── App.css                  # Component styles
    │   ├── ImportsPage.jsx          # Reference passage upload/manage page
    │   ├── ImportsPage.css
    │   ├── main.jsx                 # React entry point
    │   └── index.css                # Global reset
    ├── vite.config.js               # Dev-server proxy: /api → http://127.0.0.1:8000
    └── package.json
```

### Frontend–backend communication

The Vite dev server proxies every request beginning with `/api` to the Django server at `http://127.0.0.1:8000`. The React app therefore makes calls to `/api/analyze/` without ever specifying a host or port, which means no CORS headers are involved in development.

```js
// vite.config.js
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
},
```

In Django, `django-cors-headers` is also configured to allow `http://localhost:5173` for cases where the proxy is bypassed (e.g. direct API testing). All API responses are JSON only (`DEFAULT_RENDERER_CLASSES` contains only `JSONRenderer`).

### Model loading — AppConfig.ready()

All six NLP models are loaded **once at Django startup** using the singleton pattern. `AppConfig.ready()` is the correct Django hook because it runs after all apps are fully registered, before any request is served.

```python
# assistive_writing_coach/apps.py
class AssistiveWritingCoachConfig(AppConfig):
    name = 'assistive_writing_coach'

    def ready(self):
        import os
        from django.conf import settings
        from .services.candidate_generator import _get_tight, _get_wide, load_wikipedia_misspellings
        from .services.reranker_service import _load as load_reranker
        from .services.error_classifier_service import _get_model as load_classifier
        from .services.nli_aligner_service import _load as load_nli
        from .services.retrieval_service import get_encoder

        _get_tight()                          # SymSpell max_ed=2
        _get_wide()                           # SymSpell max_ed=4
        wiki_path = os.path.join(settings.BASE_DIR, "data", "wikipedia_misspellings.txt")
        load_wikipedia_misspellings(wiki_path) # 4,310-entry dict
        load_reranker()                        # T5-small (model + tokenizer)
        load_classifier()                      # RandomForest .joblib
        load_nli()                             # DeBERTa-v2 (model + tokenizer)
        get_encoder()                          # paraphrase-MiniLM-L3-v2
```

Each service module holds its loaded objects in module-level private variables (e.g. `_model`, `_tokenizer`, `_sym_spell_tight`). The `_get_*()` / `_load()` functions are idempotent — they return immediately if the singleton is already loaded — so they are safe to call from both `ready()` and from a request handler.

---

## 3. Full Data Flow

### Spelling analysis (POST /api/analyze/)

```
User types text in textarea
        │
        ▼
React: axios.post('/api/analyze/', { text })
        │
        ▼
Django AnalyzeView.post()
  → AnalyzeRequestSerializer validates text (min_length=1, max_length=2000)
  → calls analyze(text) from pipeline.py
        │
        ▼
pipeline.analyze(text)
  1. _tokenize(text)             — regex r"[A-Za-z]+" → list of (word, start, end)
  2. For each token:
     a. is_known_word(word)      — SymSpell lookup at max_ed=0; skip if known
     b. get_candidates(word)     — 3-layer candidate pool (see §6)
     c. candidates[0]==word?     — if best candidate == word itself, skip
     d. rerank(word, candidates) — T5-small picks best from candidate list
     e. _apply_reranker_fallbacks(word, reranked, candidates)
                                 — 4 sanity checks on edit distance + char coverage
     f. classify_error(word, best) — RandomForest predicts error type + confidence
     g. Append error dict to errors[]
        │
        ▼
Returns JSON to React
        │
        ▼
React augments each error with { applied: false, originalCorrection: e.correction }
Renders: HighlightedText (colour-coded marks) + ErrorCard list + stats bar
```

### Contextual alignment (POST /api/alignment/)

```
User clicks "Check Alignment" (only visible when a passage is selected)
        │
        ▼
React: axios.post('/api/alignment/', { text, reference_passage })
  note: text is the current textarea value (may include user-applied corrections)
        │
        ▼
Django AlignmentView.post()
  → AlignmentRequestSerializer validates both fields
  → calls run_alignment(text, reference_passage)
        │
        ▼
alignment_pipeline.run_alignment(text, reference_passage)
  1. spaCy: split reference_passage → ref_sentences[]
  2. spaCy: split text            → learner_sentences[]
  3. For each learner_sent:
     a. retrieve_best_sentence(learner_sent, ref_sentences)
        → MiniLM encodes all sentences (L2-normalised embeddings)
        → dot product = cosine similarity
        → returns (best_ref_sentence, similarity_score)
     b. align(best_ref_sentence, learner_sent)
        → DeBERTa-v2 classifies entailment / contradiction / neutral / off_topic
     c. Append { learner_sentence, reference_sentence, similarity_score,
                 nli_label, nli_confidence }
        │
        ▼
React renders ContextAlignmentSection: colour-coded NLI cards per sentence
```

### API request and response shapes

**POST /api/analyze/**

Request:
```json
{ "text": "The quik brwon fox jmped ovr the lzy dog." }
```

Response:
```json
{
  "original_text": "The quik brwon fox jmped ovr the lzy dog.",
  "corrected_text": "The quick brown fox jumped over the lazy dog.",
  "word_count": 9,
  "error_count": 5,
  "processing_time_ms": 840,
  "errors": [
    {
      "word": "quik",
      "start": 4,
      "end": 8,
      "error_type": "omission",
      "error_type_label": "Letter Omission",
      "error_type_confidence": 0.87,
      "correction": "quick",
      "candidates": ["quick", "quiz", "quill", "quilk", "quirk"],
      "feedback": "You omitted a letter."
    }
  ]
}
```

**POST /api/alignment/**

Request:
```json
{
  "text": "The fox jumped over the fence quickly.",
  "reference_passage": "A quick brown fox leapt over a tall fence. It moved swiftly through the field."
}
```

Response:
```json
{
  "context_alignment_results": [
    {
      "learner_sentence": "The fox jumped over the fence quickly.",
      "reference_sentence": "A quick brown fox leapt over a tall fence.",
      "similarity_score": 0.8912,
      "nli_label": "entailment",
      "nli_confidence": 0.7834
    }
  ]
}
```

---

## 4. NLP Components

### 4.1 T5-small Reranker

**Problem it solves**

SymSpell produces candidates ranked by (edit_distance ASC, frequency DESC). This ranking is accurate for typical keyboard-slip errors but fails for dyslexia-specific patterns where the correct word may have edit distance 3 or 4 from the misspelled form. The reranker is a seq2seq model trained to *select the correct word from the candidate list* given the misspelled word as context.

**Training data**

- Birkbeck Spelling Error Corpus (Mitton, 1985): adult learner misspelling pairs
- TOEFL-Spell (Flor et al., 2019): non-native English learner spelling errors

Combined and filtered: **22,150 training samples**, **2,769 test samples**. Candidates for each training example were generated with SymSpell and shuffled to prevent position-bias (the model must learn to select, not memorise position).

**Model architecture**

Google T5-small (Text-To-Text Transfer Transformer, Raffel et al., 2020). Encoder-decoder architecture; the spelling correction task is framed as:

```
Input:  "correct: quik options: quick | quirk | quiz | quill | quilk"
Output: "quick"
```

The model is fine-tuned to generate the correct candidate token given this prompt format. Beam search (num_beams=4) is used at inference. If the generated token is not in the candidate list, the pipeline falls back to `candidates[0]`.

**Key inference code**

```python
# reranker_service.py
def rerank(misspelled: str, candidates: list[str]) -> str:
    model, tokenizer = _load()
    candidate_str = " | ".join(candidates)
    input_text = f"correct: {misspelled} options: {candidate_str}"

    inputs = tokenizer(input_text, return_tensors="pt", max_length=128, truncation=True)
    with torch.no_grad():
        output_ids = model.generate(inputs["input_ids"], max_new_tokens=32,
                                    num_beams=4, early_stopping=True)
    result = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip().lower()

    if result in candidates:
        return result
    return candidates[0]  # fallback if generation produces out-of-vocabulary token
```

**Example**

| Misspelled | Candidates | Reranker output |
|---|---|---|
| `recieved` | `received`, `relieved`, `receiver`, `recited`, `deceived` | `received` |
| `becuz` | `because`, `became`, `becut`, `becat`, `beckon` | `because` |

**Evaluation metrics** (from `trained_models/reranker/final_model/evaluation_metrics.json`):

| Metric | Value |
|---|---|
| Top-1 accuracy on test set | **85.77%** |
| Candidate coverage on test set | **100%** (correct word always in candidate pool) |
| Test samples | 2,769 |

---

### 4.2 RandomForest Error Classifier

**Problem it solves**

Given a confirmed (misspelled word, correction) pair, classify which of five dyslexia-associated error types the misspelling represents, so the UI can show the learner targeted feedback (e.g. "You swapped two adjacent letters" rather than just "Spelling error").

**Error type labels and their linguistic basis**

| Label | Description | Example |
|---|---|---|
| `phonetic_sub` | Letter substituted with phonetically similar one | `fone` → `phone` |
| `reversal` | One or more letters written in reverse | `b` written as `d`; `was` → `saw` |
| `omission` | A letter is missing from the word | `begining` → `beginning` |
| `insertion` | An extra letter was added | `thhe` → `the` |
| `transposition` | Two adjacent letters are swapped | `recieve` → `receive` |

Labels were assigned programmatically using rules derived from the dyslexia literature (Miles, 1993; Snowling, 2000; Shaywitz, 2003).

**Training data**

Birkbeck Spelling Error Corpus (Mitton, 1985). After label assignment: **23,670 training samples** (after SMOTE oversampling to balance classes). Test split uses **unique (misspelled, correct) pairs only** to prevent data leakage — if a pair appears in training, it cannot appear in the test set regardless of oversampling.

**Feature vector (17 features)**

```python
# feature_extractor.py — extract_features(misspelled, correct) → list[float]

raw_edit_distance              # Levenshtein distance (int cast to float)
normalized_edit_distance       # raw_ed / max(len(mis), len(cor))
length_difference_signed       # len(misspelled) - len(correct)  [+ve = insertion, -ve = omission]
absolute_length_difference     # abs(len difference)
soundex_equal                  # 1.0 if Soundex codes match (phonetic proxy)
metaphone_equal                # 1.0 if Metaphone codes match (phonetic proxy)
jaro_winkler                   # Jaro-Winkler similarity (prefix-sensitive)
bigram_overlap                 # |bigrams(mis) ∩ bigrams(cor)| / |union|
trigram_overlap                # same for trigrams
positional_match               # fraction of positions where mis[i] == cor[i]
shared_char_set                # |charset(mis) ∩ charset(cor)| / |union|
mis_vowel_ratio                # vowels / len(misspelled)
cor_vowel_ratio                # vowels / len(correct)
vowel_ratio_diff               # cor_vowel_ratio - mis_vowel_ratio
misspelled_chars_not_in_correct_ratio   # chars in mis absent from cor
correct_chars_not_in_misspelled_ratio   # chars in cor absent from mis
edit_distance_to_length_diff_ratio      # raw_ed / (|length_diff| + 1)
```

**Key inference code**

```python
# error_classifier_service.py
def classify_error(misspelled: str, correct: str) -> dict:
    model = _get_model()
    features = np.array(extract_features(misspelled, correct)).reshape(1, -1)
    pred = model.predict(features)[0]
    proba = model.predict_proba(features)[0]
    return {
        "error_type": str(pred),
        "label": _LABEL_DESCRIPTIONS[pred],
        "confidence": round(float(proba.max()), 4),
        "probabilities": {cls: round(float(p), 4) for cls, p in zip(model.classes_, proba)},
    }
```

**Example**

Input: `misspelled="thhe"`, `correct="the"`

- `length_difference_signed` = +1 (insertion: misspelled is longer)
- `raw_edit_distance` = 1
- Prediction: `insertion` (confidence ~0.92)

**Evaluation metrics** (from `trained_models/error_classifier/training_metadata.json`):

| Metric | Value |
|---|---|
| Weighted F1 on test set | **0.981** |
| 5-fold CV F1 mean | **0.981 ± 0.002** |
| Unseen pair accuracy | **0.706** |
| Training samples (balanced) | 23,670 |
| Test samples (unique pairs) | 5,278 |

The *unseen pair accuracy* (0.706) is the conservative metric: only (misspelled, correct) pairs that never appeared in training — before or after oversampling — are evaluated. This is the number that matters for generalisation.

---

### 4.3 DeBERTa-v2 NLI Aligner

**Problem it solves**

After spelling errors are corrected, the question remains: *does this sentence actually fit the context of the passage the learner is writing about?* An NLI model receives a reference sentence as **premise** and the learner's corrected sentence as **hypothesis**, and classifies the logical relationship.

**Training data**

Fine-tuned on a 4-class schema derived from MultiNLI (Williams et al., 2018) and SNLI (Bowman et al., 2015) with the addition of an `off_topic` class for sentence pairs with no lexical or semantic overlap.

**Label schema**

| Label | Meaning | UI display |
|---|---|---|
| `entailment` | Learner's sentence is consistent with the reference | "Fits context" (green) |
| `contradiction` | Learner's sentence contradicts the reference | "Conflicts" (red) |
| `neutral` | Neither consistent nor contradictory; plausible but not confirmed | "Neutral" (grey) |
| `off_topic` | Learner's sentence shares no meaningful semantic content with the reference | "Off-topic" (purple) |

**Model architecture**

Microsoft DeBERTa-v2 (He et al., 2021). DeBERTa improves upon BERT and RoBERTa through *disentangled attention* (content and position are encoded separately) and an *enhanced mask decoder* that adds absolute position information at the output. This gives stronger performance on NLI benchmarks.

The model is loaded as `AutoModelForSequenceClassification` with 4 output classes.

**Key inference code**

```python
# nli_aligner_service.py
def align(context: str, corrected_sentence: str) -> dict:
    model, tokenizer = _load()
    inputs = tokenizer(context, corrected_sentence,
                       return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = F.softmax(logits, dim=-1)[0]
    pred_id = int(probs.argmax().item())
    return {
        "label": _ID2LABEL[pred_id],
        "confidence": round(float(probs[pred_id].item()), 4),
        "scores": {_ID2LABEL[i]: round(float(p.item()), 4) for i, p in enumerate(probs)},
    }
```

**Example**

- Premise: `"A quick brown fox leapt over a tall fence."`
- Hypothesis: `"The fox jumped over the fence quickly."`
- Result: `entailment` (confidence ~0.78)

---

## 5. RAG-Based Contextual Alignment

The alignment pipeline implements a two-stage **Retrieval-Augmented Generation** approach: first retrieve the most relevant reference sentence, then run NLI only on that sentence pair. This avoids the computational cost of NLI over the full reference passage and ensures the NLI premise is maximally relevant.

### Stage 1 — Sentence segmentation

Both the learner's text and the reference passage are segmented into individual sentences using spaCy `en_core_web_sm`.

```python
# alignment_pipeline.py
def _split_sentences(text: str) -> list[str]:
    doc = _get_nlp()(text)
    return [s.text.strip() for s in doc.sents if s.text.strip()]
```

### Stage 2 — Retrieval (paraphrase-MiniLM-L3-v2)

For each learner sentence, `retrieve_best_sentence()` encodes all reference sentences and the learner sentence using the MiniLM model, then selects the reference sentence with the highest cosine similarity.

```python
# retrieval_service.py
def retrieve_best_sentence(query_sentence, reference_sentences):
    encoder = get_encoder()
    query_emb = encoder.encode([query_sentence], normalize_embeddings=True)
    ref_embs  = encoder.encode(reference_sentences, normalize_embeddings=True)

    # Because embeddings are L2-normalised, dot product == cosine similarity
    scores = (ref_embs @ query_emb.T).flatten()
    best_idx = int(np.argmax(scores))
    return reference_sentences[best_idx], float(scores[best_idx])
```

L2 normalisation is applied so that the dot product is equivalent to cosine similarity, avoiding an explicit division.

### Stage 3 — NLI (DeBERTa-v2)

The retrieved reference sentence is passed as the **premise** and the learner's current sentence (with all accepted spelling corrections applied) as the **hypothesis**. The corrected version is used — not the original misspelled text — because the DeBERTa model was trained on grammatical English. Passing misspelled tokens as the hypothesis introduces out-of-distribution noise that degrades NLI accuracy.

```
Premise   (reference):  "A quick brown fox leapt over a tall fence."
Hypothesis (learner):   "The fox jumped over the fence quickly."
→ entailment (0.78)
```

```
Premise   (reference):  "The cat sat quietly on the mat."
Hypothesis (learner):   "The dog barked loudly all night."
→ contradiction (0.81)
```

### Why this design instead of full-passage NLI

Running NLI with the full reference passage as the premise would produce unreliable results because:
1. Most transformer NLI models are trained on sentence pairs, not paragraph-level inputs.
2. The DeBERTa model has a 512-token maximum; a long reference passage would be truncated.
3. Retrieving the most semantically similar sentence first gives the NLI model the *most relevant* context, which produces more discriminating predictions.

---

## 6. Candidate Generation Pipeline

For every misspelled word, the system builds a **candidate pool** in three ordered layers before passing it to the reranker.

```
misspelled word
      │
      ▼
Layer 1 — SymSpell tight (max_ed=2, Verbosity.CLOSEST)
      │  Returns closest matches sorted by (edit_distance ASC, frequency DESC)
      │  Up to 5 candidates
      ▼
Layer 2 — SymSpell wide (max_ed=4, Verbosity.ALL)  [triggered when pool is thin or top match is at distance 2]
      │  Expands with all words within edit distance 4
      │  Adds to pool up to 10 total
      ▼
Layer 3 — Wikipedia Common Misspellings lookup
      │  Dict lookup: wikipedia_misspelling_lookup[word.lower()]
      │  Appended only if not already in pool
      ▼
Candidate pool → T5-small reranker → best candidate
      │
      ▼
_apply_reranker_fallbacks(word, best, candidates)
```

### Why each layer exists

**Tight SymSpell (max_ed=2)** handles the common case: most keyboard slips and simple dyslexic reversals and transpositions are within 2 edits of the correct word. Using `Verbosity.CLOSEST` limits the pool to the statistically best options without introducing noise.

**Wide SymSpell (max_ed=4)** handles phonetic substitutions like `becuz` → `because` (edit distance 3) and `skool` → `school` (edit distance 3) where the tight lookup returns no useful candidates. Wide expansion is only triggered when the pool is thin (`len(seen) < 5`) or the best tight candidate is already at maximum tight distance (`top_distance >= 2`).

**Wikipedia misspellings** is a 4,310-entry lookup of real-world phonetic and orthographic errors curated from Wikipedia's machine-readable common misspellings list. It captures words like `wuz`, `definately`, `occured` that SymSpell's frequency-ranked candidates de-prioritise because the correct word is far in edit-distance space. It is appended *last* so the reranker still sees SymSpell's frequency-ranked candidates first.

### Reranker fallback checks

After the T5-small model generates a correction, four sanity checks prevent obviously wrong picks:

```python
# pipeline.py — _apply_reranker_fallbacks(word, reranked, candidates)

ed_reranked = editdistance.eval(word_lower, reranked)
ed_top      = editdistance.eval(word_lower, candidates[0])

# Check 0a: reranker chose a word further from input than candidates[0]
if ed_reranked > ed_top:
    return candidates[0]

# Check 0b: same edit distance but fewer shared characters with input
if ed_reranked == ed_top and reranked != candidates[0]:
    miss_reranked = sum(1 for c in word_lower if c not in set(reranked))
    miss_top      = sum(1 for c in word_lower if c not in set(candidates[0]))
    if miss_reranked > miss_top:
        return candidates[0]

# Check 1: reranked word is 2+ characters shorter than misspelled word
if len(reranked) < len(word_lower) - 1:
    longer = next((c for c in candidates if len(c) >= len(word_lower)), None)
    if longer:
        return longer

# Check 2: edit distance exceeds half the misspelled word's length
if ed_reranked > len(word_lower) / 2:
    return candidates[0]

return reranked
```

| Check | Catches |
|---|---|
| 0a — edit distance rank | `lteter→better` (ed=3) when `letter` (ed=2) is available |
| 0b — character coverage | `scohol→spool` (ed=2, missing c,h) when `school` (ed=2, missing 0 chars) is available |
| 1 — length sanity | `importnt→import` (7→6 chars, suspiciously short) |
| 2 — edit distance ceiling | Any pick whose edit distance is more than half the word length — statistically implausible |

---

## 7. Setup and Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- A virtual environment tool (venv, conda, etc.)

### Backend setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 2. Install Python dependencies
pip install django djangorestframework django-cors-headers
pip install transformers torch sentencepiece
pip install sentence-transformers spacy
pip install symspellpy editdistance jellyfish joblib scikit-learn numpy
pip install pymupdf python-docx   # PDF and DOCX extraction

# 3. Download spaCy model
python -m spacy download en_core_web_sm

# 4. Place trained models
# The backend/trained_models/ directory must contain:
#   reranker/final_model/        — T5-small fine-tuned weights
#   error_classifier/            — error_classifier.joblib + training_metadata.json
#   nli_model/final_model/       — DeBERTa-v2 fine-tuned weights

# 5. Place Wikipedia misspellings file
# backend/data/wikipedia_misspellings.txt
# Format: one entry per line — "misspelling->correction"

# 6. Run database migrations
cd backend
python manage.py migrate

# 7. Start Django development server
python manage.py runserver
# Server starts at http://127.0.0.1:8000
# All models load at startup — watch the console for [STARTUP] messages
```

### Frontend setup

```bash
cd frontend
npm install
npm run dev
# Vite dev server starts at http://localhost:5173
# All /api/* requests are proxied to http://127.0.0.1:8000
```

Open `http://localhost:5173` in a browser.

### Environment variables

Create `backend/.env` with the following (do not commit this file — it is listed in `.gitignore`):

```env
GROQ_API_KEY=your_groq_api_key_here
```

The `GROQ_API_KEY` is required for Filipino spelling analysis and all Taglish conversion modes. Obtain a key at [console.groq.com](https://console.groq.com). Without it the system operates in English-only mode — no error is raised, the fallback is silent.

The only other configurable path is:

```python
# backend/salitayo/settings.py
TRAINED_MODELS_DIR = os.path.join(BASE_DIR, 'trained_models')
```

Change this if the trained models are stored elsewhere.

### Verifying startup

When Django starts successfully, the console prints:

```
[STARTUP] Pre-loading NLP models...
[STARTUP] SymSpell tight (max_ed=2) ready.
[STARTUP] SymSpell wide (max_ed=4) ready.
[STARTUP] Wikipedia misspellings lookup ready.
[STARTUP] T5 reranker ready.
[STARTUP] RandomForest classifier ready.
[STARTUP] DeBERTa NLI aligner ready.
[STARTUP] Sentence encoder (MiniLM) ready.
[STARTUP] All models loaded.
```

The first analysis request after startup will respond in approximately 1–2 seconds (CPU inference). Subsequent requests are faster because all models remain in memory.

### API health check

```
GET http://127.0.0.1:8000/api/health/
→ { "status": "ok" }
```

---

## 8. Known Limitations

**Phonetic substitutions that change word length**

Words like `fone` (phone) have edit distance 2 and also differ in length from the correct form. The length difference can push the error classifier toward `omission` rather than `phonetic_sub` if the phonetic features (Soundex, Metaphone) are insufficient to discriminate. This is a known edge case in the 17-feature vector — the two phonetic features are binary (match/no-match) and do not capture degree of phonetic similarity.

**Reranker failure on rare phonetic substitutions**

The T5 reranker was trained on Birkbeck + TOEFL-Spell, which are adult learner corpora. Novel phonetic substitution patterns that appear frequently in child writers with dyslexia but rarely in adult learner data may not be well-represented in training. When the correct word does not appear in the SymSpell + Wikipedia candidate pool at all, no model component can recover the correct answer.

**NLI confidence degrades at low retrieval similarity**

If the learner's sentence is entirely off-topic relative to the reference passage (e.g. a sentence about weather in a history passage), the MiniLM retrieval returns the least-dissimilar reference sentence — which may still have low similarity (< 0.3). The DeBERTa model then receives a premise and hypothesis with no semantic overlap, and the `off_topic` prediction is correct, but the confidence is often low (0.4–0.5) because the model is uncertain between `neutral` and `off_topic`. The UI displays `off_topic` as purple; this is informative but should be interpreted cautiously at low similarity.

**Training corpus bias toward adult learners**

The Birkbeck Spelling Error Corpus and TOEFL-Spell dataset were collected from adult learners (university students and EFL test takers). Dyslexic children may produce error patterns that are underrepresented, particularly gross phonetic substitutions (e.g. `skool`, `wuz`) and full-word reversals. The Wikipedia misspellings fallback partially compensates for this gap, but the classifier's 70.6% unseen-pair accuracy should be understood in this context.

**No grammar checking**

SALITAyo is a **spelling error detector only**. It does not check grammar. Errors such as subject-verb disagreement (`she go` instead of `she goes`), wrong tense, incorrect word order, missing articles, and similar grammatical mistakes are outside scope and will not be flagged. Only orthographic errors — wrong letters, missing letters, extra letters, reversed letters, transposed letters — are detected.

**Taglish conversion may produce grammatically incorrect output**

The Filipino and Taglish pipelines use Groq LLM inference (llama-3.3-70b-versatile) to replace words or phrases with their target-language equivalents. Because corrections are computed word-by-word or phrase-by-phrase against the original token positions, the model does not restructure the full sentence to match the target language's grammar. This can produce output that is lexically correct but grammatically awkward — for example, word order may remain anchored to the source language, or function words (articles, prepositions, particles) may not fully agree with adjacent translated content. The suggestions should be treated as a starting point for revision, not as grammatically guaranteed output.

**Groq dependency for Filipino and Taglish**

Filipino spelling analysis and all Taglish conversion modes require a valid `GROQ_API_KEY` in `backend/.env`. If the key is absent or the Groq API is unavailable, the system silently falls back to the English NLP pipeline for all inputs. No error is surfaced to the user; the response will simply reflect English-only analysis.

**Single-word analysis only**

The English spelling pipeline operates on individual alphabetic tokens (`r"[A-Za-z]+"`) with no sentence context. Context-dependent errors (e.g. `there` vs `their`) are outside scope and are not detected.

**2,000-character input limit**

The `AnalyzeRequestSerializer` enforces `max_length=2000` on the text field. Longer inputs must be submitted in segments.

---

## 9. Datasets and Citations

**Birkbeck Spelling Error Corpus**
> Mitton, R. (1985). *Birkbeck spelling error corpus*. Oxford Text Archive. Used as the primary source of (misspelled, correct) pairs for both the RandomForest classifier and the T5 reranker. Labels for dyslexia error types were assigned programmatically using rules from the dyslexia literature.

**TOEFL-Spell**
> Flor, M., Futagi, Y., Lopez, M., & Mulholland, M. (2019). *Span-based grammatical error correction*. TOEFL Research Report. Used as supplementary training data for the T5 reranker (non-native English learner spelling errors).

**MultiNLI**
> Williams, A., Nangia, N., & Bowman, S. R. (2018). A broad-coverage challenge corpus for sentence understanding through inference. *NAACL-HLT 2018*. Used as the base training corpus for the DeBERTa NLI model, providing entailment, contradiction, and neutral examples across diverse genres.

**SNLI**
> Bowman, S. R., Angeli, G., Potts, C., & Manning, C. D. (2015). A large annotated corpus for learning natural language inference. *EMNLP 2015*. Combined with MultiNLI to provide additional entailment/contradiction training signal for the NLI fine-tuning.

**Wikipedia Common Misspellings**
> Wikipedia contributors. *Wikipedia:Lists of common misspellings/For machines*. Wikimedia Foundation. Licensed under CC BY-SA 4.0. Used as the third-layer phonetic fallback dictionary (4,310 entries, `misspelling->correction` format).

**SymSpell frequency dictionary**
> Garbe, W. (2018). *SymSpell: 1 million times faster through Symmetric Delete spelling correction algorithm*. GitHub. The `frequency_dictionary_en_82_765.txt` bundled with the `symspellpy` package (82,765 English words with corpus frequencies) is used as the SymSpell dictionary for both the tight and wide instances.

**DeBERTa-v2**
> He, P., Liu, X., Gao, J., & Chen, W. (2021). DeBERTa: Decoding-enhanced BERT with disentangled attention. *ICLR 2021*. The base model architecture used for the NLI aligner.

**T5**
> Raffel, C., Shazeer, N., Roberts, A., Lee, K., Narang, S., Matena, M., Zhou, Y., Li, W., & Liu, P. J. (2020). Exploring the limits of transfer learning with a unified text-to-text transformer. *JMLR 21(140)*, 1–67. The base model architecture used for the reranker.

**paraphrase-MiniLM-L3-v2**
> Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. *EMNLP 2019*. The sentence encoder used for RAG retrieval.

---

*SALITAyo — developed as part of an undergraduate thesis in Information Technology, University of San Jose-Recoletos, Cebu City, Philippines.*
