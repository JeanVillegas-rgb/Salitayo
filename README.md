# SALITAyo Reading Restructurer

> **SALITAyo Reading Restructurer** is a web-based reading support tool for learners with dyslexia. It restructures academic or dense text into shorter, clearer, dyslexia-friendly chunks while preserving important names, acronyms, and key terms. It supports English, Tagalog, and mixed-language output, with optional speech playback and adaptive diagnostic signals.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Full Data Flow](#3-full-data-flow)
4. [Core Components](#4-core-components)
5. [Local Model Loading](#5-local-model-loading)
6. [Adaptive Reading Support](#6-adaptive-reading-support)
7. [API Reference](#7-api-reference)
8. [Setup and Installation](#8-setup-and-installation)
9. [Known Limitations](#9-known-limitations)
10. [Datasets and Citations](#10-datasets-and-citations)

---

## 1. Project Overview

### Who it is for

The Reading Restructurer is designed for learners who struggle with long academic passages, dense sentence structure, complex vocabulary, or visual reading load. The learner pastes or uploads text and receives:

- simplified academic text,
- sentence-per-line chunks,
- preserved names, acronyms, and important terms,
- optional English, Tagalog, or mixed output,
- clickable word augmentation in the frontend,
- text-to-speech playback per chunk,
- adaptive diagnostic feedback based on replay and reading behavior.

### Research gaps addressed

| Gap | Description | Component |
|-----|-------------|-----------|
| Gap 1 | Many reading tools enlarge text but do not restructure sentence complexity. This project simplifies wording and sentence form. | `services.py`, `restructurer_inference.py` |
| Gap 2 | Dyslexic readers benefit from visual chunking, but ordinary paragraphs often remain visually dense. This tool returns sentence-level chunks for easier scanning. | `_build_chunks_from_text()` |
| Gap 3 | Simplification can accidentally change proper nouns, acronyms, or academic anchor terms. This system protects named entities and preserved terms. | `ner.py`, `_extract_preserved_terms()` |
| Gap 4 | Filipino learners may read English, Tagalog, or mixed Taglish material. The tool supports `en`, `tl`, and `mix` targets. | `ReadingRestructurer.jsx`, `services.py` |
| Gap 5 | Static simplification does not react to reading difficulty. This tool records replay and progress signals and exposes adaptive levers. | `diagnostic_log`, frontend session metrics |

### Tech stack and justification

| Technology | Role | Why |
|---|---|---|
| Django + Django REST Framework | Backend API | Provides request validation, multipart upload handling, and JSON API responses. |
| React + Vite | Frontend SPA | Gives a fast interactive interface for input, output chunks, language controls, and TTS. |
| Hugging Face Transformers | Local seq2seq inference | Loads local T5/mT5-style restructuring models from `backend/models/`. |
| PyTorch | Model runtime | Runs the local seq2seq model on CPU or CUDA when available. |
| BERT NER (`dslim/bert-base-NER`) | Term protection | Detects names, organizations, locations, and important capitalized terms to preserve. |
| spaCy | Sentence and grammar support | Used when available for sentence processing and verb detection. |
| Groq API | LLM simplification and audio support | Used for hosted language processing and neural TTS when configured. |
| NLTK | Evaluation metrics | Computes readability and simplification metrics such as FKGL, BLEU, and SARI. |
| SQLite | Local database | Keeps the local development setup self-contained. |

---

## 2. System Architecture

### Folder structure

```text
restructurer/
|-- backend/
|   |-- manage.py
|   |-- db.sqlite3
|   |-- wp.sqlite3
|   |-- requirements.txt
|   |-- restructurer_inference.py
|   |-- synonyms.json
|   |
|   |-- salitayo/
|   |   |-- settings.py
|   |   |-- urls.py
|   |   |-- wsgi.py
|   |   `-- asgi.py
|   |
|   |-- restructurer/
|   |   |-- views.py
|   |   |-- urls.py
|   |   |-- serializers.py
|   |   |-- services.py
|   |   |-- corpus.py
|   |   |-- ner.py
|   |   |-- evaluation.py
|   |   |-- training_engine.py
|   |   |-- training_data.py
|   |   `-- management/
|   |       `-- commands/
|   |           |-- bootstrap_dataset.py
|   |           |-- evaluate_model.py
|   |           `-- train_t5.py
|   |
|   |-- rag_corpus/
|   |   |-- dyslexia_friendly_guidelines.md
|   |   `-- philippines_bilingual_awareness.md
|   |
|   `-- models/
|       |-- t5_restructurer/
|       |-- t5_restructurer_updated/
|       |-- tagalog_restructurer/
|       `-- tagalog_open_topic_restructurer/
|
`-- frontend/
    |-- package.json
    |-- vite.config.js
    `-- src/
        |-- App.jsx
        |-- ReadingRestructurer.jsx
        |-- diagnostics.css
        |-- styles.css
        `-- main.jsx
```

### Frontend-backend communication

The frontend calls the Django API through Vite's proxy:

```js
// frontend/vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```

This lets the React app call `/api/restructure/` from the browser while Django runs on `http://localhost:8000`.

### Django URL mounting

```python
# backend/salitayo/urls.py
urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("api/", include("restructurer.urls")),
]
```

The restructurer app exposes:

```python
# backend/restructurer/urls.py
urlpatterns = [
    path("", home, name="home"),
    path("restructure/", RestructureTextView.as_view(), name="restructure-text"),
    path("tts-speech/", tts_speech, name="tts-speech"),
]
```

---

## 3. Full Data Flow

### Reading restructure request

```text
User enters or uploads academic text
        |
        v
React ReadingRestructurer.jsx
  -> POST /api/restructure/
  -> sends input_text, source_context, target_language, mixed_output
        |
        v
Django RestructureTextView.post()
  -> RestructureRequestSerializer validates text or file
  -> extracts .txt, .pdf, or .docx content when needed
  -> calls ReadingRestructurerService.restructure()
        |
        v
ReadingRestructurerService
  1. computes adaptive levers
  2. detects protected terms with BERT NER + heuristics
  3. optionally translates protected anchors
  4. simplifies text through hosted/local pipeline
  5. calls local model through restructurer_inference.py when available
  6. normalizes whitespace and cleans artifacts
  7. splits output into sentence chunks
  8. computes evaluation and diagnostic metadata
        |
        v
JSON response
        |
        v
React renders:
  - full restructured text
  - sentence chunks
  - model mode badge
  - adaptive diagnostic log
  - clickable word augmentation
  - per-chunk speech button
```

### Text-to-speech request

```text
User clicks speaker button on a chunk
        |
        v
React builds /api/tts-speech/?text=...&lang=...
        |
        v
Django tts_speech()
  -> calls service.generate_groq_audio(text, lang)
        |
        v
Returns audio/mpeg when Groq audio succeeds
        |
        v
Frontend plays neural audio
        |
        v
If neural audio fails, browser speechSynthesis is used as fallback
```

---

## 4. Core Components

### 4.1 Request serializer

`backend/restructurer/serializers.py` accepts either direct text or an uploaded file.

Supported inputs:

- `input_text`
- UTF-8 `.txt`
- `.pdf`
- `.docx`

The serializer extracts readable text and guarantees that the service receives a non-empty `input_text`.

### 4.2 ReadingRestructurerService

`backend/restructurer/services.py` is the main orchestration layer. It handles:

- language detection,
- adaptive reading levers,
- RAG guidance loading,
- BERT NER protection,
- protected-term extraction,
- simplification,
- local model restructuring,
- chunk generation,
- Tagalog purification,
- diagnostic metadata,
- response formatting.

### 4.3 Local inference module

`backend/restructurer_inference.py` loads local seq2seq models and exposes:

```python
predict(text, lang="en", protected_terms=None) -> dict
```

It returns:

```json
{
  "raw": "...",
  "cleaned": "...",
  "model_key": "default"
}
```

For English, it uses prompts like:

```text
restructure: The samples were analyzed by the researchers.
```

For Tagalog, it uses prompts like:

```text
restructure fil: ...
```

### 4.4 BERT NER protection

`backend/restructurer/ner.py` uses `dslim/bert-base-NER` when available, then merges model results with heuristic entity detection.

Protected terms include:

- people,
- locations,
- organizations,
- acronyms,
- capitalized proper names,
- multi-word proper names.

These terms are passed into the simplification and model pipeline so they are less likely to be rewritten incorrectly.

### 4.5 RAG guidance corpus

`backend/restructurer/corpus.py` loads `.md` files from `backend/rag_corpus/` and retrieves the most relevant guidance by token overlap.

Current corpus files:

- `dyslexia_friendly_guidelines.md`
- `philippines_bilingual_awareness.md`

The corpus is used as lightweight retrieval support for dyslexia-friendly and bilingual reading guidance.

### 4.6 Evaluation metrics

`backend/restructurer/evaluation.py` computes:

- FKGL original,
- FKGL simplified,
- FKGL delta,
- BLEU,
- SARI-style keep/delete/add rates,
- `readability_improved`.

These metrics are returned as diagnostic support rather than as final proof of pedagogical quality.

---

## 5. Local Model Loading

The local model is loaded through `backend/restructurer_inference.py`.

### English model search order

```text
RESTRUCTURER_MODEL_DIR
backend/models/t5_restructurer_updated/
backend/models/t5_restructurer/
```

### Tagalog model search order

```text
TAGALOG_RESTRUCTURER_MODEL_DIR
backend/models/tagalog_restructurer/
backend/models/mt5_tagalog_restructurer/
backend/models/salitayo_tagalog_restructurer/
backend/models/salitayo_tagalog_v3_candidate_model/
backend/models/tagalog_open_topic_restructurer/
```

### Required model files

A model directory is considered usable when it contains:

- `config.json`
- at least one weight file such as:
  - `model.safetensors`
  - `pytorch_model.bin`
  - `pytorch_model-*.bin`
  - `pytorch_model.bin.index.json`
  - `flax_model.msgpack`

### Runtime behavior

The model loader:

- uses CUDA when available, otherwise CPU,
- caches loaded models in `MODEL_CACHE`,
- uses `T5TokenizerFast.from_pretrained("t5-small")` for the default English model,
- uses local tokenizer files for Tagalog when available,
- falls back to deterministic restructuring if model output is empty, invalid, or too close to the input.

---

## 6. Adaptive Reading Support

The frontend and backend expose adaptive signals intended to describe learner reading difficulty.

### Observational metrics

| Metric | Meaning | Trigger |
|---|---|---|
| RR | Replay Rate | Increases when the learner replays audio chunks. |
| ToC | Time on Chunk Ratio | Represents time spent relative to expected baseline. |
| VFI | Vocabulary Friction Index | Represents vocabulary difficulty signals. |
| SDP | Session Drop Point | Tracks how far through the chunks the learner progressed. |

### Adaptive levers

| Lever | Behavior |
|---|---|
| Chunk size | Smaller chunks when replay rate is high. |
| Playback speed | Slower speech when time-on-chunk is high. |
| Aggressiveness | More aggressive simplification when progress is low. |

### Frontend reading aids

The React interface provides:

- language toggles for English, Tagalog, and Mixed,
- mixed-output target selection,
- sentence cards,
- active chunk focus,
- per-chunk audio playback,
- clickable word hyphenation,
- model-mode badges,
- diagnostic log display.

---

## 7. API Reference

### POST `/api/restructure/`

Request:

```json
{
  "input_text": "The samples were analyzed by the researchers.",
  "source_context": "reading simplification",
  "target_language": "en",
  "mixed_output": "taglish"
}
```

You can also send `input_file` using `multipart/form-data`.

Supported `target_language` values:

| Value | Meaning |
|---|---|
| `en` | English output |
| `tl` | Tagalog output |
| `mix` | Mixed-language output |

Supported `mixed_output` values:

| Value | Meaning |
|---|---|
| `taglish` | Taglish mixed output |
| `tagalog` | Pure Tagalog target |
| `english` | Pure English target |

Response:

```json
{
  "success": true,
  "input_text": "The samples were analyzed by the researchers.",
  "restructured_text": "- The researchers analyzed the samples.",
  "mode": "local-model",
  "augmented_words": [],
  "chunks": [
    {
      "chunk_id": "chunk-1",
      "text": "- The researchers analyzed the samples.",
      "highlight_terms": [],
      "color_terms": []
    }
  ],
  "metadata": {
    "font_family": "OpenDyslexic, Atkinson Hyperlegible, sans-serif",
    "text_size": "1.15rem",
    "layout": "sentence-per-line",
    "bilingual_awareness": true,
    "preserved_terms": [],
    "mode": "local-model"
  },
  "diagnostic_log": {
    "status": "success",
    "mode": "local-model",
    "engine": "SALITAyo-Stable-V2"
  }
}
```

### GET `/api/tts-speech/`

Request:

```text
/api/tts-speech/?text=The%20researchers%20analyzed%20the%20samples.&lang=en
```

Response:

- `audio/mpeg` on success,
- JSON error response on failure.

---

## 8. Setup and Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- Local model files if using offline restructuring
- Groq API key if using hosted LLM or neural audio features

### Backend setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The backend runs at:

```text
http://localhost:8000
```

### Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at:

```text
http://localhost:5173
```

### Environment variables

Create `backend/.env` when needed:

```env
GROQ_API_KEY=your_groq_api_key_here
RESTRUCTURER_MODEL_DIR=C:\path\to\english\model
TAGALOG_RESTRUCTURER_MODEL_DIR=C:\path\to\tagalog\model
```

`RESTRUCTURER_MODEL_DIR` and `TAGALOG_RESTRUCTURER_MODEL_DIR` are optional if the models are stored in one of the default `backend/models/` folders.

### Quick API test

```bash
curl -X POST http://localhost:8000/api/restructure/ ^
  -H "Content-Type: application/json" ^
  -d "{\"input_text\":\"The samples were analyzed by the researchers.\",\"target_language\":\"en\"}"
```

---

## 9. Known Limitations

**Local models are not included by default**

The code expects local model folders under `backend/models/` or paths supplied through environment variables. If the required files are missing, local model inference cannot run.

**Tagalog quality depends on available model or API behavior**

Tagalog restructuring uses the Tagalog model when present. If no Tagalog model is available, the system may rely on hosted processing or fallback behavior.

**NER protection is best-effort**

BERT NER and heuristic protection reduce unwanted changes to names and acronyms, but they cannot guarantee that every technical term is preserved.

**PDF extraction depends on document quality**

Scanned PDFs without embedded text may not extract cleanly through `PyPDF2`.

**Evaluation metrics are approximate**

FKGL, BLEU, and SARI are useful signals, but they do not fully measure whether a dyslexic learner understands the restructured text.

**Browser TTS fallback varies by device**

If Groq audio fails, the frontend uses `speechSynthesis`. Voice quality and Tagalog support depend on the browser and operating system.

**Very long passages may be truncated or split**

The local T5-style model uses a 512-token input limit. Long text is processed sentence by sentence, but extremely long or malformed sentences may still lose detail.

---

## 10. Datasets and Citations

**T5**
> Raffel, C., Shazeer, N., Roberts, A., Lee, K., Narang, S., Matena, M., Zhou, Y., Li, W., & Liu, P. J. (2020). Exploring the limits of transfer learning with a unified text-to-text transformer. *Journal of Machine Learning Research, 21*(140), 1-67.

**mT5**
> Xue, L., Constant, N., Roberts, A., Kale, M., Al-Rfou, R., Siddhant, A., Barua, A., & Raffel, C. (2021). mT5: A massively multilingual pre-trained text-to-text transformer. *NAACL 2021*.

**BERT**
> Devlin, J., Chang, M.-W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. *NAACL-HLT 2019*.

**Text simplification evaluation**
> Xu, W., Napoles, C., Pavlick, E., Chen, Q., & Callison-Burch, C. (2016). Optimizing statistical machine translation for text simplification. *Transactions of the Association for Computational Linguistics, 4*, 401-415.

**Dyslexia-friendly reading support**
> British Dyslexia Association. Dyslexia Style Guide. Used as a practical reference for readability choices such as spacing, chunking, and accessible typography.

---

*SALITAyo Reading Restructurer - developed as part of an assistive learning system for dyslexic learners.*
