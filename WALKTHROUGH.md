# SALITAyo — Writing Assistant: Full Script & Walkthrough

> A detailed, code-level walkthrough of every feature, mechanism, and design decision in the system.

---

## Table of Contents

1. [What SALITAyo Is](#1-what-salitayo-is)
2. [System Architecture at a Glance](#2-system-architecture-at-a-glance)
3. [How the App Starts Up](#3-how-the-app-starts-up)
4. [The NLP Pipeline — Layer by Layer](#4-the-nlp-pipeline--layer-by-layer)
   - [Layer 1: Tokenization](#layer-1-tokenization)
   - [Layer 2: Candidate Generation (3-Tier Pool)](#layer-2-candidate-generation-3-tier-pool)
   - [Layer 3: T5-small Seq2Seq Reranker](#layer-3-t5-small-seq2seq-reranker)
   - [Layer 4: Reranker Fallback Checks](#layer-4-reranker-fallback-checks)
   - [Layer 5: RandomForest Error Type Classifier](#layer-5-randomforest-error-type-classifier)
5. [Contextual Alignment: RAG + NLI](#5-contextual-alignment-rag--nli)
   - [Stage 1: Sentence Segmentation](#stage-1-sentence-segmentation)
   - [Stage 2: Semantic Retrieval (MiniLM)](#stage-2-semantic-retrieval-miniLM)
   - [Stage 3: NLI Classification (DeBERTa-v2)](#stage-3-nli-classification-deberta-v2)
6. [Multilingual Support — Filipino & Taglish](#6-multilingual-support--filipino--taglish)
7. [The API Layer (Django REST)](#7-the-api-layer-django-rest)
8. [The Frontend (React)](#8-the-frontend-react)
9. [Full End-to-End Data Flow (Annotated)](#9-full-end-to-end-data-flow-annotated)
10. [Live Demo Walkthrough Script](#10-live-demo-walkthrough-script)
11. [Design Decisions & Why They Matter](#11-design-decisions--why-they-matter)
12. [Known Limitations](#12-known-limitations)
13. [Quick Reference](#13-quick-reference)

---

## 1. What SALITAyo Is

SALITAyo is a **dyslexia-aware assistive writing coach** for Filipino learners. Unlike generic spell-checkers that only flag errors, SALITAyo:

- **Detects** spelling errors in English, Filipino, and Taglish text
- **Classifies** *what kind* of error each one is (phonetic substitution, reversal, omission, insertion, transposition)
- **Generates** pedagogically targeted feedback based on the error type
- **Checks** whether the learner's writing is semantically consistent with a reference passage the teacher uploaded

The core research insight is this: most assistive tools tell a dyslexic learner **that** something is wrong. SALITAyo tells them **how** it is wrong — which is the basis for remediation.

**Tech stack at a glance:**

| Layer | Technology |
|---|---|
| Backend | Django 6.0.5 + Django REST Framework |
| NLP (English) | SymSpell, T5-small, RandomForest, DeBERTa-v2, MiniLM |
| NLP (Filipino) | Groq API (llama-3.3-70b-versatile) |
| Frontend | React 19 + Vite 8 |
| Database | SQLite (reference passages) |

---

## 2. System Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                     BROWSER (React 19)                  │
│                                                         │
│   [Input Textarea] → [Analyze Button]                   │
│   [Language Selector: Auto / Filipino / English]        │
│   [Reference Passage Selector]                          │
│                                                         │
│   ← Results: Highlighted text, Error cards, Alignment   │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP (Vite proxy /api → :8000)
┌───────────────────────────▼─────────────────────────────┐
│                  Django REST API (:8000)                 │
│                                                         │
│  POST /api/analyze/      → AnalyzeView                  │
│  POST /api/alignment/    → AlignmentView                │
│  GET  /api/passages/     → PassageListView              │
│  POST /api/passages/extract/ → PassageExtractView       │
│  DELETE /api/passages/<id>/delete/ → PassageDeleteView  │
└──────┬──────────────────────────┬───────────────────────┘
       │ English                  │ Filipino / Taglish
┌──────▼──────────┐    ┌──────────▼──────────────┐
│  NLP Pipeline   │    │   Groq LLM API           │
│                 │    │   llama-3.3-70b          │
│  1. Tokenize    │    │   temperature=0.1         │
│  2. Candidates  │    └─────────────────────────-┘
│     (SymSpell   │
│      + Wiki)    │
│  3. T5 Rerank   │
│  4. Fallbacks   │
│  5. Classify    │
└──────┬──────────┘
       │
┌──────▼──────────────────────────────────┐
│   Contextual Alignment (optional)       │
│                                         │
│  spaCy → sentence split                 │
│  MiniLM → cosine similarity retrieval   │
│  DeBERTa-v2 → NLI 4-way classification │
└─────────────────────────────────────────┘
```

---

## 3. How the App Starts Up

**File:** `backend/assistive_writing_coach/apps.py`

All six ML models are loaded **once** when Django starts, before any request is served. This is done in `AppConfig.ready()`:

```python
class AssistiveWritingCoachConfig(AppConfig):
    name = 'assistive_writing_coach'

    def ready(self):
        _get_tight()                    # SymSpell, max_edit_distance=2
        _get_wide()                     # SymSpell, max_edit_distance=4
        load_wikipedia_misspellings()   # 4,310 word pairs from data/
        load_reranker()                 # T5-small from trained_models/reranker/
        load_classifier()              # RandomForest from trained_models/error_classifier/
        load_nli()                     # DeBERTa-v2 from trained_models/nli_model/
        get_encoder()                  # paraphrase-MiniLM-L3-v2
```

Using `AppConfig.ready()` ensures all models are in memory before the first API call arrives. Each loader uses a singleton pattern (check if already loaded → return early), so it is safe to call from both startup and request handlers.

**Startup time on first run:** ~30–60 seconds (downloads + caching model weights).  
**Subsequent starts:** ~5–10 seconds (loading from disk).  
**Request latency after startup:** < 1 second (all models in RAM).

---

## 4. The NLP Pipeline — Layer by Layer

**File:** `backend/assistive_writing_coach/services/pipeline.py`

The main entry point is `analyze(text: str) -> dict`. It iterates over every token, runs it through five sequential stages, and aggregates the results.

---

### Layer 1: Tokenization

```python
def _tokenize(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end())
            for m in re.finditer(r"[A-Za-z]+", text)]
```

The regex `[A-Za-z]+` captures only alphabetic characters — numbers, punctuation, and spaces are ignored. Each match returns the word itself plus its **byte offsets** in the original string.

**Why offsets matter:** The frontend uses these exact start/end positions to render colour-coded underlines on the correct character ranges without any frontend re-parsing.

**Example:**

```
Input: "She recieved the lettre."

Tokens:
  ('She',      0,  3)
  ('recieved', 4, 12)
  ('the',     13, 16)
  ('lettre',  17, 23)
```

---

### Layer 2: Candidate Generation (3-Tier Pool)

**File:** `backend/assistive_writing_coach/services/candidate_generator.py`

For each token, the pipeline first calls `is_known_word()` — which uses SymSpell's frequency dictionary to check if the word is valid. If it is unknown, it calls `get_candidates()` to build a pool of plausible corrections.

The candidate pool is assembled in three ordered tiers:

#### Tier 1 — SymSpell Tight (max_edit_distance = 2)

```python
tight_suggestions = tight.lookup(
    word_lower,
    Verbosity.CLOSEST,
    max_edit_distance=2
)
```

SymSpell pre-computes a "delete neighbourhood" from the frequency dictionary, enabling sub-millisecond lookup for any word within edit distance 2. Results are sorted by `(edit_distance ASC, word_frequency DESC)`.

This tier catches the vast majority of keyboard slips and simple dyslexic errors.

#### Tier 2 — SymSpell Wide (max_edit_distance = 4)

Only triggered when:
- The tight pool has fewer than 5 candidates, **or**
- The best tight candidate is already at edit distance 2 (the tight ceiling)

```python
needs_expansion = len(seen) < max_candidates or top_distance >= 2
if needs_expansion:
    wide_suggestions = wide.lookup(word_lower, Verbosity.ALL, max_edit_distance=4)
```

Expanding to edit distance 4 catches phonetic substitutions that change multiple letters, such as:

```
"becuz" → candidates include "because" (edit distance 3)
```

#### Tier 3 — Wikipedia Common Misspellings

```python
wiki_suggestion = wikipedia_misspelling_lookup.get(word_lower)
if wiki_suggestion and wiki_suggestion not in seen:
    seen.append(wiki_suggestion)
```

A dictionary of 4,310 misspelling→correction pairs loaded from `data/wikipedia_misspellings.txt`. Added **last** so frequency-ranked SymSpell candidates take priority. Catches established non-standard forms like:

```
"wuz" → "was"   (not found by SymSpell's statistical model)
```

**Final output:** A deduplicated list of 5–10 candidate corrections, ready for reranking.

---

### Layer 3: T5-small Seq2Seq Reranker

**File:** `backend/assistive_writing_coach/services/reranker_service.py`

**Problem:** SymSpell ranks by edit distance and word frequency — it has no concept of spelling correction *patterns*. A purely frequency-ranked list will prefer common short words over the contextually correct correction.

**Solution:** A T5-small model fine-tuned on 22,150 spelling error samples from the Birkbeck Spelling Error Corpus and TOEFL-Spell. It learns to pick the correction that best fits the error pattern.

#### Inference

```python
def rerank(misspelled: str, candidates: list[str]) -> str:
    candidate_str = " | ".join(candidates)
    input_text = f"correct: {misspelled} options: {candidate_str}"

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        max_length=128,
        truncation=True
    )
    with torch.no_grad():
        output_ids = model.generate(
            inputs["input_ids"],
            max_new_tokens=32,
            num_beams=4
        )
    result = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip().lower()

    return result if result in candidates else candidates[0]  # fallback
```

**Prompt format:**

```
"correct: recieved options: received | relieved | receiver | recited"
```

The model generates a single token (the chosen correction) using beam search with 4 beams. If the output token is not in the candidate list — a safety net — the system falls back to `candidates[0]` (SymSpell's top-ranked word).

**Model performance:**
- Test accuracy (top-1): **85.77%** on 2,769 held-out samples
- Candidate coverage: **100%** — the correct word is always present in the pool

---

### Layer 4: Reranker Fallback Checks

**File:** `pipeline.py → _apply_reranker_fallbacks()`

The reranker is accurate but not infallible. Four deterministic checks prevent the most common failure modes:

| Check | Condition | Action | Why |
|---|---|---|---|
| **0a — ED Rank** | `ed(reranked, word) > ed(candidates[0], word)` | Return `candidates[0]` | Reranker chose something *further* from the input than SymSpell's best — statistically implausible |
| **0b — Char Coverage** | Same edit distance, but reranker shares fewer characters | Return `candidates[0]` | At equal edit distance, prefer the candidate preserving more of the original letters |
| **1 — Length** | `len(reranked) < len(word) - 1` | Find next-longer candidate | Reranker's pick is suspiciously short (e.g. `"importnt"` → `"import"` instead of `"important"`) |
| **2 — ED Ceiling** | `ed(reranked, word) > len(word) / 2` | Return `candidates[0]` | Edit distance exceeds half the word length — the correction is likely unrelated to the input |

These checks act as a deterministic safety layer around the probabilistic neural model.

---

### Layer 5: RandomForest Error Type Classifier

**Files:**
- `backend/assistive_writing_coach/services/error_classifier_service.py`
- `backend/assistive_writing_coach/services/feature_extractor.py`

**Problem:** Once we know a word is misspelled and what the correction is, we need to answer: *what kind of error did the learner make?* This drives the pedagogical feedback.

#### The 5 Error Types

| Label | Description | Example |
|---|---|---|
| `phonetic_sub` | Letter replaced with a phonetically similar one | `"fone"` → `"phone"` |
| `reversal` | One or more letters written mirror-image | `"was"` ↔ `"saw"` |
| `omission` | A letter is missing | `"begining"` → `"beginning"` |
| `insertion` | An extra letter was added | `"thhe"` → `"the"` |
| `transposition` | Two adjacent letters are swapped | `"recieved"` → `"received"` |

#### 17-Feature Vector

The classifier does **not** learn directly from raw strings. Instead, `feature_extractor.py` converts each (misspelled, correction) pair into a 17-dimensional vector of interpretable linguistic signals:

```python
def extract_features(misspelled: str, correct: str) -> list[float]:

    # --- Edit distance signals ---
    raw_edit_distance              # Levenshtein(misspelled, correct)
    normalized_edit_distance       # raw_ed / max(len_mis, len_cor)
    edit_distance_to_length_diff   # raw_ed / (|len_mis - len_cor| + 1)

    # --- Length signals ---
    length_difference_signed       # len(mis) - len(cor)  [+ve = insert, -ve = omit]
    absolute_length_difference     # |len_mis - len_cor|

    # --- Phonetic signals ---
    soundex_equal                  # 1.0 if Soundex codes match, else 0.0
    metaphone_equal                # 1.0 if Metaphone codes match, else 0.0

    # --- String similarity ---
    jaro_winkler                   # Jaro-Winkler similarity (0.0–1.0)
    bigram_overlap                 # |bigrams(mis) ∩ bigrams(cor)| / |union|
    trigram_overlap                # |trigrams(mis) ∩ trigrams(cor)| / |union|
    positional_match               # fraction of positions where mis[i] == cor[i]
    shared_char_set                # |charset(mis) ∩ charset(cor)| / |union|

    # --- Vowel signals ---
    mis_vowel_ratio                # vowels / len(mis)
    cor_vowel_ratio                # vowels / len(cor)
    vowel_ratio_diff               # cor_vowel_ratio - mis_vowel_ratio

    # --- Character set difference ---
    mis_chars_not_in_cor_ratio     # chars in mis absent from cor / len(mis)
    cor_chars_not_in_mis_ratio     # chars in cor absent from mis / len(cor)
```

**Why handcrafted features instead of embeddings?**

RandomForest with engineered features is:
- **Interpretable** — each tree split can be traced to a meaningful signal
- **Fast** — CPU inference, no GPU required
- **Compact** — the saved model is a few hundred KB, not gigabytes
- **Highly accurate** — F1 (weighted) of **0.981** on the test set

#### Worked Example — `"recieved"` → `"received"`

```
raw_edit_distance        = 2     (swap i↔e at positions 3–4)
normalized_edit_distance = 0.25  (2/8)
length_difference_signed = 0     (same length — not omission/insertion)
soundex_equal            = 1.0   (both → R213)
jaro_winkler             = 0.944 (very high — only 2 chars different)
positional_match         = 0.75  (6/8 positions identical)
shared_char_set          = 1.0   (no novel or missing letters)
```

**Prediction: `transposition` (confidence ≈ 0.95)**

#### Inference

```python
def classify_error(misspelled: str, correct: str) -> dict:
    model = _get_model()
    features = np.array(extract_features(misspelled, correct)).reshape(1, -1)

    pred  = model.predict(features)[0]           # e.g. "transposition"
    proba = model.predict_proba(features)[0]      # probabilities for all 5 classes

    return {
        "error_type":   pred,
        "label":        _LABEL_DESCRIPTIONS[pred],
        "confidence":   round(max(proba), 4),
        "probabilities": {cls: round(p, 4)
                          for cls, p in zip(model.classes_, proba)},
    }
```

---

## 5. Contextual Alignment: RAG + NLI

**Files:**
- `backend/assistive_writing_coach/services/alignment_pipeline.py`
- `backend/assistive_writing_coach/services/retrieval_service.py`
- `backend/assistive_writing_coach/services/nli_aligner_service.py`

This feature answers the question: **"Does what the learner wrote make sense given the reference material?"**

It is a two-stage pipeline: first **retrieve** the most relevant sentence from the reference passage, then **classify** the semantic relationship between the two sentences.

This feature is **opt-in** — it only runs when the user selects a reference passage before analyzing their text.

---

### Stage 1: Sentence Segmentation

```python
def _split_sentences(text: str) -> list[str]:
    doc = _get_nlp()(text)   # spaCy en_core_web_sm
    return [s.text.strip() for s in doc.sents if s.text.strip()]
```

SpaCy's `en_core_web_sm` pipeline uses a combination of statistical models and rule-based heuristics to detect sentence boundaries. Both the learner's text and the reference passage are split into sentences before anything else — because the retrieval and NLI models operate at the **sentence-pair level**, not document level.

---

### Stage 2: Semantic Retrieval (MiniLM)

**File:** `retrieval_service.py`

**Model:** `paraphrase-MiniLM-L3-v2`
- 384-dimensional sentence embeddings
- ~17 MB on disk
- Fine-tuned on paraphrase and sentence-similarity datasets

```python
def retrieve_best_sentence(
    query_sentence: str,
    reference_sentences: list[str]
) -> tuple[str, float]:

    encoder = get_encoder()   # singleton SentenceTransformer

    query_emb = encoder.encode([query_sentence], normalize_embeddings=True)
    ref_embs  = encoder.encode(reference_sentences, normalize_embeddings=True)

    # L2-normalized embeddings → dot product == cosine similarity
    scores    = (ref_embs @ query_emb.T).flatten()
    best_idx  = int(np.argmax(scores))

    return reference_sentences[best_idx], float(scores[best_idx])
```

**Why this step before NLI?**

DeBERTa (the NLI model) is expensive. Running it on every possible (learner sentence × reference sentence) pair would be O(n × m). Retrieval reduces this to O(1) NLI calls per learner sentence by pre-selecting the single most relevant reference sentence using the lightweight MiniLM encoder.

The similarity score from this step is also surfaced in the UI so the user can see how closely matched the retrieved reference sentence is.

---

### Stage 3: NLI Classification (DeBERTa-v2)

**File:** `nli_aligner_service.py`

**Model:** DeBERTa-v2 (`microsoft/deberta-v2-xlarge-mnli`)  
**Fine-tuned on:** MultiNLI + SNLI + custom `off_topic` label (4-way classification)

```python
def align(context: str, corrected_sentence: str) -> dict:
    model, tokenizer = _load()

    inputs = tokenizer(
        context, corrected_sentence,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )
    with torch.no_grad():
        logits = model(**inputs).logits
        probs  = F.softmax(logits, dim=-1)[0]

    pred_id = int(probs.argmax().item())
    return {
        "label":      _ID2LABEL[pred_id],
        "confidence": round(float(probs[pred_id].item()), 4),
        "scores":     {_ID2LABEL[i]: round(float(p.item()), 4)
                       for i, p in enumerate(probs)},
    }
```

**Important:** The NLI model receives the **corrected** learner sentence, not the original misspelled one. DeBERTa was trained on grammatical English, and passing misspelled tokens introduces out-of-distribution noise that degrades accuracy.

#### The 4 Labels

| Label | Meaning | UI Display |
|---|---|---|
| `entailment` | Learner sentence is consistent with the reference | Green — "Fits context" |
| `contradiction` | Learner sentence contradicts the reference | Red — "Conflicts" |
| `neutral` | Related but makes a distinct claim (neither confirms nor denies) | Grey — "Neutral" |
| `off_topic` | No meaningful semantic connection to the reference | Purple — "Off-topic" |

The `off_topic` class is custom — it does not exist in standard NLI datasets. It was added to handle the real-world case where a learner's sentence is simply about a completely different subject.

**Why DeBERTa over BERT or RoBERTa?**

DeBERTa uses **disentangled attention** — content and position are encoded in separate vectors and their interaction is computed explicitly. This lets the model capture both the *what* (content) and the *where* (position) of a word's relationship to its context, which significantly improves performance on natural language inference tasks.

---

## 6. Multilingual Support — Filipino & Taglish

**Files:**
- `backend/assistive_writing_coach/services/filipino_pipeline.py`
- `backend/assistive_writing_coach/views.py` → `_classify_input()`

### Language Routing

Before any analysis, `_classify_input()` determines which pipeline to invoke:

```python
def _classify_input(text: str, target_language: str) -> str:
    if not GROQ_API_KEY:
        return "english"        # Silent fallback if key missing

    if target_language == "english":
        return "taglish_to_english"
    if target_language == "filipino":
        return "taglish_to_filipino"

    # Auto mode: use statistical language detection
    try:
        langs    = detect_langs(text)
        lang_dict = {l.lang: l.prob for l in langs}
        has_en   = lang_dict.get("en", 0) > 0.15
        has_tl   = lang_dict.get("tl", 0) > 0.15
        is_mix   = has_en and has_tl
        dominant = max(lang_dict, key=lang_dict.get)
    except Exception:
        is_mix   = False
        dominant = "en"

    if is_mix:
        return "taglish_to_filipino"
    return "filipino" if dominant == "tl" else "english"
```

**Four possible routing outcomes:**

| Route | When | What Happens |
|---|---|---|
| `english` | Pure English detected | Full NLP pipeline (SymSpell → T5 → RF) |
| `filipino` | Pure Filipino detected | Groq LLM detects Filipino spelling errors |
| `taglish_to_english` | User selected "English" explicitly | Groq converts Taglish → English + fixes spelling |
| `taglish_to_filipino` | User selected "Filipino" OR auto-detected Taglish | Groq converts Taglish → Filipino + fixes spelling |

### Why Groq Instead of a Trained Model?

The English pipeline (T5-small, RandomForest) was trained on the **Birkbeck Spelling Error Corpus** and **TOEFL-Spell** — both are English-only datasets totalling ~22,000 samples. No equivalent annotated corpus exists for Filipino dyslexic learner errors. Creating one from scratch is a full research project in itself.

Groq's `llama-3.3-70b-versatile` already has multilingual pretraining and knows Filipino grammar and common spelling patterns. With `temperature=0.1` (near-deterministic), it produces consistent, focused corrections. This is a pragmatic solution to a real research gap.

### Groq Inference Flow

```python
def _run_groq(text: str, prompt_template: str, language_key: str) -> dict:
    client = _get_client()
    prompt = prompt_template.replace('"{text}"', f'"{text}"')

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=1024,
    )

    content   = resp.choices[0].message.content
    raw_errors = _parse_response(content)    # Extract JSON array from LLM output
    errors     = _compute_positions(text, raw_errors)  # Find character offsets

    # Apply corrections with running offset tracking
    corrected = text
    offset    = 0
    for err in errors:
        adj_start = err["start"] + offset
        adj_end   = err["end"]   + offset
        best      = err["correction"]
        corrected = corrected[:adj_start] + best + corrected[adj_end:]
        offset   += len(best) - (err["end"] - err["start"])

    return {
        "original_text":      text,
        "corrected_text":     corrected,
        "word_count":         ...,
        "error_count":        len(errors),
        "errors":             errors,
        "processing_time_ms": ...,
        "language":           language_key,
    }
```

The **running offset** is critical: as corrections are applied left-to-right, each substitution changes the length of the string. Without tracking the cumulative offset, all subsequent character positions would be wrong.

### The Three Groq Prompt Templates

**`analyze_filipino(text)`** — Pure Filipino spell-checking:
```
Ikaw ay isang spelling error detector para sa mga mag-aaral na may dyslexia 
na sumusulat sa Filipino o Tagalog.

Suriin ang teksto para sa mga spelling error sa Filipino/Tagalog na mga salita 
lamang. Para sa bawat error, ibalik ang JSON na may: word, correction, 
error_type, confidence, candidates, feedback.
```

**`analyze_taglish_to_english(text)`** — Taglish → English conversion + fix:
```
You are an English writing assistant for Filipino dyslexic learners writing in Taglish.

Convert the text to pure English by replacing every Filipino/Tagalog word with its 
correct English equivalent AND fixing any misspelled English words.

IMPORTANT: If two or more consecutive words together form a single meaning, return 
the entire phrase as ONE entry.
```

**`analyze_taglish_to_filipino(text)`** — Taglish → Filipino conversion + fix:
Same structure, but targets Filipino as the output language.

---

## 7. The API Layer (Django REST)

**Files:**
- `backend/assistive_writing_coach/views.py`
- `backend/assistive_writing_coach/serializers.py`
- `backend/assistive_writing_coach/urls.py`

### Endpoints

| Method | Route | View Class | Purpose |
|---|---|---|---|
| POST | `/api/analyze/` | `AnalyzeView` | Run spelling analysis |
| POST | `/api/alignment/` | `AlignmentView` | Run contextual alignment |
| GET | `/api/health/` | `HealthView` | Health check |
| GET | `/api/passages/` | `PassageListView` | List reference passages |
| POST | `/api/passages/extract/` | `PassageExtractView` | Upload & extract PDF/DOCX |
| GET | `/api/passages/<id>/` | `PassageDetailView` | Fetch passage content |
| DELETE | `/api/passages/<id>/delete/` | `PassageDeleteView` | Delete passage |

### Request/Response Shapes

**POST `/api/analyze/`**

Request:
```json
{
  "text": "The quik brwon fox jmped ovr the lzy dog.",
  "target_language": "auto"
}
```

Response:
```json
{
  "original_text": "The quik brwon fox jmped ovr the lzy dog.",
  "corrected_text": "The quick brown fox jumped over the lazy dog.",
  "word_count": 9,
  "error_count": 5,
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
      "feedback": "You omitted a letter. The word 'quik' is missing a letter that appears in 'quick'."
    }
  ],
  "processing_time_ms": 840,
  "language": "english"
}
```

**POST `/api/alignment/`**

Request:
```json
{
  "text": "The fox jumped over the fence quickly.",
  "reference_passage": "A quick brown fox leapt over a tall fence."
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

### Serializer Validation

`AnalyzeRequestSerializer` enforces:
- `text`: required, 1–2,000 characters
- `target_language`: must be one of `["auto", "english", "filipino"]`

`PassageExtractView` accepts multipart/form-data (PDF or DOCX), extracts the text using PyMuPDF (for PDF) or python-docx (for DOCX), truncates at 3,000 words, and saves to SQLite via the `Passage` model.

---

## 8. The Frontend (React)

**Files:**
- `frontend/src/App.jsx` — main UI
- `frontend/src/App.css` — 733 lines of styling
- `frontend/src/ImportsPage.jsx` — reference passage management

### Component Hierarchy

```
<App>
  ├── <Header>
  │     SALITAyo title + "Reference Passages" button
  │
  ├── <InputSection>
  │     ├── <PassageSelector>   dropdown: select or skip reference passage
  │     ├── <LanguageSelector>  pills: Auto / Filipino / English
  │     ├── <textarea>          writing area, max 2000 chars, live char counter
  │     └── <button>            "Analyze Writing"
  │
  └── [if result exists]
        ├── <LanguageBadge>     shows which pipeline ran ("English", "Filipino", etc.)
        ├── <StatsBar>          word count | errors found | errors solved
        ├── <HighlightedText>   original text with colour-coded error marks
        ├── <CorrectionPanel>   fully corrected text (updated as user applies changes)
        ├── <ErrorsList>
        │     └── [for each error] <ErrorCard>
        │           ├── misspelled word → correction
        │           ├── error type badge (colour-coded by type)
        │           ├── confidence %
        │           ├── feedback text (pedagogical explanation)
        │           ├── candidate suggestion pills (clickable)
        │           └── [if applied] Undo button
        │
        ├── <ComparisonModal>   (opens on candidate click: before/after preview)
        └── [if alignment data]
              <ContextAlignmentSection>
                └── [for each sentence pair] <AlignmentCard>
                      ├── NLI label badge + colour
                      ├── NLI confidence %
                      ├── similarity % (from MiniLM retrieval)
                      └── learner sentence vs. reference sentence
```

### Error Type Color Scheme

```javascript
const ERROR_TYPE_COLORS = {
  phonetic_sub:  '#7c3aed',   // Purple
  reversal:      '#dc2626',   // Red
  omission:      '#d97706',   // Amber
  insertion:     '#0891b2',   // Cyan
  transposition: '#16a34a',   // Green
  language_mix:  '#9333ea',   // Violet (Groq-returned Taglish errors)
}
```

### NLI Result Display Config

```javascript
const NLI_CONFIG = {
  entailment:    { label: 'Fits context', color: '#16a34a', bg: '#f0fdf4' },
  contradiction: { label: 'Conflicts',    color: '#dc2626', bg: '#fef2f2' },
  neutral:       { label: 'Neutral',      color: '#6b7280', bg: '#f8fafc' },
  off_topic:     { label: 'Off-topic',    color: '#9333ea', bg: '#faf5ff' },
}
```

### HighlightedText Component

This is the visual core of the error display. Using the `start` and `end` positions returned by the API, the component slices the original text and wraps each error span in a `<mark>` tag:

```jsx
function HighlightedText({ text, errors }) {
  // Builds an array of text segments and <mark> elements
  // Each <mark> has a CSS custom property --err-color matching the error type
  // Hovering shows a tooltip: "Error Type: misspelled → correction"
}
```

Because the positions come directly from the tokenizer (which captured byte offsets from the original string), no frontend re-parsing is necessary.

### Applying Candidate Suggestions

When a user clicks a candidate pill on an ErrorCard:
1. A `ComparisonModal` opens showing before/after context with the substituted word highlighted
2. If the user confirms, the error's `correction` field is updated in React state
3. The `CorrectionPanel` recomputes the full corrected text by replaying all applied corrections left-to-right with offset tracking (same logic as the backend's Groq pipeline)
4. The `StatsBar` increments "errors solved"
5. An Undo button appears on the card

---

## 9. Full End-to-End Data Flow (Annotated)

```
1. USER types text in the textarea
   e.g.: "She recieved a lettre from her frend."

2. USER selects language (Auto / Filipino / English)
   e.g.: Auto

3. USER clicks "Analyze Writing"

4. REACT calls:
   axios.post('/api/analyze/', {
     text: "She recieved a lettre from her frend.",
     target_language: "auto"
   })

5. VITE PROXY forwards to http://127.0.0.1:8000/api/analyze/

6. DJANGO AnalyzeView.post() receives request
   └─ AnalyzeRequestSerializer validates: text length OK, target_language valid

7. _classify_input("She recieved...", "auto")
   └─ langdetect detects "en" dominant, no "tl"
   └─ Returns: "english"

8. pipeline.analyze("She recieved a lettre from her frend.")

   For token "She" (0, 3):
     is_known_word("she") → True → skip

   For token "recieved" (4, 12):
     is_known_word("recieved") → False
     get_candidates("recieved")
       Tier 1: ["received", "relieved", "receiver", "recited", "reclined"]
       Tier 2: no expansion needed (5 candidates found)
       Tier 3: no Wikipedia entry
       Pool: ["received", "relieved", "receiver", "recited", "reclined"]

     rerank("recieved", pool)
       Input: "correct: recieved options: received | relieved | receiver | recited | reclined"
       T5 generates: "received"
       "received" is in pool → return "received"

     _apply_reranker_fallbacks("recieved", "received", pool)
       ed("received", "recieved") = 2
       ed("received", "recieved") ≤ ed("received", "recieved") → Check 0a: PASS
       Length check: len("received") = 8 = len("recieved") → Check 1: PASS
       ED ceiling: 2 ≤ 8/2 = 4 → Check 2: PASS
       Return: "received"

     classify_error("recieved", "received")
       Features: ed=2, len_diff=0, soundex_equal=1.0, positional_match=0.75, ...
       RandomForest predicts: "transposition" (confidence: 0.948)
       Return: {error_type: "transposition", confidence: 0.948, ...}

     Error object:
       {word: "recieved", start: 4, end: 12,
        correction: "received", error_type: "transposition",
        error_type_confidence: 0.948,
        candidates: ["received", "relieved", "receiver", "recited", "reclined"],
        feedback: "Two adjacent letters were swapped. ..."}

   [Same process for "lettre" → "letter" and "frend" → "friend"]

9. RESPONSE JSON returned to React:
   {
     original_text: "She recieved a lettre from her frend.",
     corrected_text: "She received a letter from her friend.",
     word_count: 7,
     error_count: 3,
     errors: [ ...3 error objects... ],
     processing_time_ms: 620,
     language: "english"
   }

10. REACT augments each error:
    error.applied = false
    error.originalCorrection = error.correction

11. REACT renders:
    - StatsBar: 7 words | 3 errors found | 0 solved
    - HighlightedText: "recieved" underlined green, "lettre" underlined amber,
      "frend" underlined amber
    - ErrorCards: one per error, with type badges, candidates, feedback
    - CorrectionPanel: "She received a letter from her friend."

12. USER clicks candidate "friend" on frend's ErrorCard
    → ComparisonModal: "She received a letter from her [friend]."
    → USER confirms
    → error.correction updated, StatsBar: 1 solved

[OPTIONAL: User selects reference passage, clicks "Check Alignment"]

13. REACT calls:
    axios.post('/api/alignment/', {
      text: corrected_text,
      reference_passage: passage.content
    })

14. DJANGO AlignmentView.post()
    └─ alignment_pipeline.run_alignment(corrected_text, reference_passage)

    spaCy splits learner text into sentences
    spaCy splits reference passage into sentences

    For each learner sentence:
      retrieve_best_sentence(sentence, ref_sentences)
        → MiniLM encodes both, dot product → best_ref, score=0.82

      align(best_ref, sentence)
        → DeBERTa-v2 classifies pair
        → {label: "entailment", confidence: 0.79}

15. REACT renders ContextAlignmentSection:
    For each sentence:
      AlignmentCard showing NLI badge (green "Fits context"),
      confidence 79%, similarity 82%,
      side-by-side learner vs. reference sentences
```

---

## 10. Live Demo Walkthrough Script

> This section is written as a spoken script for a live demo or presentation. Numbered steps map to UI actions.

---

**[OPEN THE APP]**

"This is SALITAyo — a writing assistant built specifically for Filipino dyslexic learners. Let me walk you through what it does and how each part of the system works."

---

**[STEP 1 — LANGUAGE SELECTION]**

"Up here we have three language modes: Auto, Filipino, and English. In Auto mode, the system uses a statistical language detector to figure out what language the text is in. If it detects a mix of English and Filipino — what we call Taglish — it will route the text to a different pipeline. I'll show you that in a moment."

---

**[STEP 2 — TYPE ENGLISH TEXT]**

"Let me type some text that has the kinds of errors we see with dyslexic learners."

Type: `She recieved a lettre from her frend and was verry hapy.`

"Notice: *recieved* has two letters swapped. *Lettre* has the letters in a different order. *Frend* is missing a letter. *Verry* has an extra letter. *Hapy* is missing a letter."

---

**[STEP 3 — CLICK ANALYZE]**

"I'll click Analyze. The text goes to our Django backend, which runs it through a five-layer NLP pipeline."

*[Wait for results]*

"And here are the results."

---

**[STEP 4 — EXPLAIN THE STATS BAR]**

"At the top we have a summary: how many words, how many errors were found, and how many the learner has resolved. Right now it's zero resolved because we haven't done anything yet."

---

**[STEP 5 — EXPLAIN HIGHLIGHTED TEXT]**

"Here's the original text with the errors highlighted in colour. Each colour corresponds to an error type — and that's actually one of the unique things about this system. Most spell-checkers just tell you a word is wrong. SALITAyo tells you *how* it is wrong."

Point to colors:
- "Green means *transposition* — two letters were swapped"
- "Amber means *omission* — a letter is missing"
- "Cyan means *insertion* — an extra letter was added"

---

**[STEP 6 — EXPLAIN AN ERROR CARD]**

"Down here, every error gets its own card. Let's look at *recieved*."

Point to the transposition card:

"The system says this is a **transposition** error — *i* and *e* were swapped. Confidence is 94.8%. Below the error type, there's a feedback message explaining what happened — this is the pedagogical component, the 'why'."

"And here are the candidate suggestions. These come from a three-tier candidate pool: first, SymSpell searches words within edit distance 2; if it doesn't find enough candidates, it expands to edit distance 4; and finally it checks a dictionary of 4,310 Wikipedia misspellings. Then a T5-small model — a fine-tuned seq2seq transformer — picks the best one from the pool."

---

**[STEP 7 — APPLY A CORRECTION]**

"If I click on a candidate..."

*[Click 'received']*

"...I get a before-and-after comparison. If this looks right, I can confirm the change."

*[Confirm]*

"The corrected text panel updates, and the stats bar now shows one error resolved."

---

**[STEP 8 — HOW THE CLASSIFIER WORKS]**

"Let me explain what's happening under the hood for the error classification. When the pipeline has the misspelled word and its correction, it feeds them into a **RandomForest classifier**. But it doesn't feed in raw strings — it engineers a 17-dimensional feature vector first."

"Features like: edit distance, whether the Soundex codes match (a phonetic fingerprint), the fraction of positions that align, bigram and trigram overlap. This gives the model interpretable signals to work with."

"The RandomForest achieves an F1 score of 0.981 on the test set — and because it's a Random Forest, not a neural network, every decision can be traced back to a specific feature. That matters when you're building a system for educational use."

---

**[STEP 9 — UPLOAD A REFERENCE PASSAGE]**

"Now I'll show the contextual alignment feature. Let me switch to the Reference Passages page."

*[Click 'Reference Passages']*

"This is where a teacher can upload a PDF or DOCX file — for example, a chapter from a textbook, a reading passage, or an assignment brief. The system extracts the text and saves it."

*[Upload a file or select an existing passage]*

---

**[STEP 10 — CHECK ALIGNMENT]**

"Back on the main page, I select that passage from the dropdown and click *Check Alignment*."

"What happens now is a two-stage process. First, a lightweight sentence encoder — paraphrase-MiniLM-L3-v2 — encodes every sentence from the reference passage into a 384-dimensional vector. Then, for each sentence the learner wrote, it finds the most similar reference sentence using cosine similarity."

"Then — and this is the second stage — it passes that sentence pair to a DeBERTa-v2 model that classifies the **semantic relationship** between them."

*[Show alignment results]*

"The result is one of four labels: *Fits context*, *Conflicts*, *Neutral*, or *Off-topic*. Each card also shows the similarity score from the retrieval step and the confidence from DeBERTa."

---

**[STEP 11 — FILIPINO / TAGLISH]**

"Now let me show the multilingual support. Let me switch to Filipino mode and type some Taglish."

*[Select 'Filipino']*

Type: `Gusto ko mag-aral ng math pero mahirap siya.`

"In Filipino mode, the text goes to a completely different pipeline. Instead of our trained models, it's sent to Groq's API running llama-3.3-70b-versatile — a large language model — because no annotated Filipino dyslexic learner corpus exists for us to train on. This is an honest acknowledgment of a real research gap."

*[Analyze]*

"The LLM detects Filipino spelling errors and returns the same JSON structure as the English pipeline, so the frontend renders it identically."

---

**[WRAP UP]**

"So to summarize what you're seeing: a five-layer NLP pipeline for English — tokenization, candidate generation with SymSpell and Wikipedia, reranking with T5, deterministic fallback checks, and RandomForest error classification — plus a RAG-and-NLI alignment pipeline for contextual checking, plus a Groq-based pipeline for Filipino and Taglish. All of it served through a Django REST API, consumed by a React frontend that focuses on giving the learner actionable, pedagogically grounded feedback."

---

## 11. Design Decisions & Why They Matter

### Why Not a Single End-to-End Neural Model?

A single seq2seq model (like the full T5-large) could potentially learn to go from misspelled text to corrected text in one step. We didn't do this because:

1. **Interpretability**: A teacher or student needs to understand *why* a correction was made. A black-box model can't explain its reasoning.
2. **Modularity**: Each layer can be improved independently. The reranker can be retrained without touching the classifier. The classifier can be updated without retraining SymSpell.
3. **Resource constraints**: Inference on a single T5-large would require a GPU. Our pipeline (SymSpell + T5-small + RandomForest) runs comfortably on CPU.

### Why SymSpell Instead of Just a Language Model?

SymSpell operates in sub-millisecond time using pre-computed delete neighbourhoods. For real-time, character-level spelling correction with word frequency ranking, it is unmatched in speed. The neural reranker adds intelligence *on top* of SymSpell's fast candidate pool — it doesn't replace it.

### Why RandomForest Instead of a Neural Classifier?

The feature engineering step (17 interpretable features) makes the classifier's decisions traceable. When the classifier says `transposition`, we can look at the features and confirm that `length_difference=0`, `positional_match=0.75`, `shared_char_set=1.0` — all of which are exactly what you'd expect from a transposition. A neural classifier would produce the same label with less explainability.

### Why DeBERTa for NLI?

Standard BERT-based NLI models use attention that conflates content and position. DeBERTa's **disentangled attention** mechanism encodes content (what the word is) and position (where it appears) separately, then models their interaction explicitly. This is measurably better on NLI benchmarks, especially for longer or more complex sentence pairs.

### The 2,000 Character Limit

Enforced in `AnalyzeRequestSerializer`. This is a practical limit: the pipeline processes each token through multiple model calls. Longer texts increase latency roughly linearly. At 2,000 characters, the 99th percentile response time remains under 3 seconds on CPU.

---

## 12. Known Limitations

| Limitation | Detail |
|---|---|
| **No grammar checking** | Only spelling is analyzed. Subject-verb agreement, tense, and word order are out of scope. |
| **Bisaya/Cebuano not supported** | `langdetect` handles `en` and `tl` only. Cebuano would fall through to the English pipeline. |
| **Groq dependency for Filipino** | If `GROQ_API_KEY` is missing, Filipino text silently falls back to the English pipeline. |
| **Taglish grammar quality** | The Groq pipeline replaces words/phrases but does not restructure sentences. Output may be lexically correct but grammatically awkward in the target language. |
| **Low retrieval similarity → low NLI confidence** | If a learner sentence is truly off-topic, MiniLM returns the least-dissimilar reference (similarity ≈ 0.3). DeBERTa is uncertain between `neutral` and `off_topic`, yielding low confidence (0.4–0.5). The label is usually correct; the confidence reflects genuine uncertainty. |
| **Reranker edge cases** | Rare phonetic patterns not in Birkbeck/TOEFL-Spell training data may be misranked. The fallback checks partially compensate, but novel error patterns can slip through. |

---

## 13. Quick Reference

### File Map

| File | Purpose |
|---|---|
| `backend/assistive_writing_coach/services/pipeline.py` | Main spelling analysis orchestrator (5 layers) |
| `backend/assistive_writing_coach/services/candidate_generator.py` | 3-tier candidate pool (SymSpell + Wikipedia) |
| `backend/assistive_writing_coach/services/reranker_service.py` | T5-small seq2seq reranker |
| `backend/assistive_writing_coach/services/error_classifier_service.py` | RandomForest error type classifier |
| `backend/assistive_writing_coach/services/feature_extractor.py` | 17-feature vector engineering |
| `backend/assistive_writing_coach/services/alignment_pipeline.py` | RAG + NLI orchestrator |
| `backend/assistive_writing_coach/services/retrieval_service.py` | MiniLM cosine similarity retrieval |
| `backend/assistive_writing_coach/services/nli_aligner_service.py` | DeBERTa-v2 NLI classification |
| `backend/assistive_writing_coach/services/filipino_pipeline.py` | Groq LLM for Filipino / Taglish |
| `backend/assistive_writing_coach/views.py` | Django REST views + language routing |
| `backend/assistive_writing_coach/serializers.py` | Request/response validation |
| `backend/assistive_writing_coach/apps.py` | Model preloading at startup |
| `backend/data/wikipedia_misspellings.txt` | 4,310 misspelling→correction pairs |
| `frontend/src/App.jsx` | Main React UI |
| `frontend/src/ImportsPage.jsx` | Reference passage management UI |

### Model Summary

| Model | Task | Training Data | Key Metric |
|---|---|---|---|
| SymSpell (tight, ed=2) | Candidate generation | Word frequency dict | Sub-millisecond lookup |
| SymSpell (wide, ed=4) | Extended candidates | Same | Catches ed 3–4 patterns |
| T5-small | Reranking | 22,150 pairs (Birkbeck + TOEFL) | 85.77% top-1 accuracy |
| RandomForest | Error classification | ~23K pairs (SMOTE-balanced) | F1 = 0.981 |
| paraphrase-MiniLM-L3-v2 | Sentence retrieval | Paraphrase datasets | 384-dim cosine similarity |
| DeBERTa-v2 | NLI (4-way) | MultiNLI + SNLI + off_topic | Custom 4-label fine-tune |
| llama-3.3-70b (Groq) | Filipino/Taglish | Multilingual pretraining | temp=0.1, pragmatic |

### Error Type Summary

| Type | Signal | Example |
|---|---|---|
| `transposition` | Same letters, swapped adjacent pair | `recieved` → `received` |
| `omission` | Missing letter, length diff negative | `begining` → `beginning` |
| `insertion` | Extra letter, length diff positive | `thhe` → `the` |
| `reversal` | Mirror-image segment | `saw` ↔ `was` |
| `phonetic_sub` | Phonetically similar substitution | `fone` → `phone` |

### NLI Labels

| Label | Meaning | Color |
|---|---|---|
| `entailment` | Consistent with reference | Green |
| `contradiction` | Contradicts reference | Red |
| `neutral` | Related but distinct claim | Grey |
| `off_topic` | No semantic connection | Purple |

---

*SALITAyo — Assistive Writing Coach for Filipino Dyslexic Learners*
