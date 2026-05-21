# SALITAyo Workspace Map

Use this file when you need to know which folder belongs to which module.

## Main App Structure

| Area | Folder / File | Purpose |
|---|---|---|
| Frontend app | `frontend/` | React/Vite user interface |
| Backend app | `backend/` | Django REST Framework API |
| Main Django settings | `backend/salitayo/` | Project settings, URLs, DB router |
| Generated reports/files | `outputs/` | Evaluation CSV/XLSX files made during testing |
| Training notebooks | `*.ipynb` in repo root | Colab/Jupyter model training notebooks |

## Reading Restructurer

This is your main module.

| Part | Location | Notes |
|---|---|---|
| Frontend screen | `frontend/src/ReadingRestructurer.jsx` | Main Reading Restructurer UI |
| Reading diagnostics styles | `frontend/src/diagnostics.css` | Adaptive diagnostic log styling |
| Main backend service | `backend/restructurer/services.py` | Main restructuring pipeline |
| API view | `backend/restructurer/views.py` | Receives `/api/restructure/` requests |
| Request serializer | `backend/restructurer/serializers.py` | Validates input text/files |
| Evaluation metrics | `backend/restructurer/evaluation.py` | FRE, FKGL, GFI, ASL, ASW, BERTScore, ERR |
| Local model inference | `backend/restructurer_inference.py` | Loads and runs local seq2seq model |
| Reading model folders | `backend/models/` | Expected local model folders |
| RAG corpus | `backend/rag_corpus/` | Optional/context corpus folder |

Important Reading Restructurer flow:

```text
frontend/src/ReadingRestructurer.jsx
-> POST /api/restructure/
-> backend/restructurer/views.py
-> backend/restructurer/serializers.py
-> backend/restructurer/services.py
-> backend/restructurer_inference.py
-> backend/restructurer/evaluation.py
-> response returns to ReadingRestructurer.jsx
```

## Writing Assistant

This is Jure's module.

| Part | Location | Notes |
|---|---|---|
| Frontend screen | `frontend/src/WritingAssistant.jsx` | Main Writing Assistant UI |
| Frontend styles | `frontend/src/WritingAssistant.css` | Writing Assistant styling |
| Import page | `frontend/src/ImportsPage.jsx` | PDF/DOCX import screen |
| Import page styles | `frontend/src/ImportsPage.css` | Import page styling |
| Backend app | `backend/assistive_writing_coach/` | Writing Assistant backend |
| Startup loading | `backend/assistive_writing_coach/apps.py` | Preloads writing models |
| URLs | `backend/assistive_writing_coach/urls.py` | Writing Assistant API routes |
| Main views | `backend/assistive_writing_coach/views.py` | API views |
| Pipeline | `backend/assistive_writing_coach/services/pipeline.py` | Analyze/spell-check pipeline |
| Reranker | `backend/assistive_writing_coach/services/reranker_service.py` | T5 reranker |
| NLI aligner | `backend/assistive_writing_coach/services/nli_aligner_service.py` | DeBERTa NLI aligner |
| Model folders | `backend/trained_models/` | Writing Assistant model files |

Expected Writing Assistant model folders:

```text
backend/trained_models/reranker/final_model/
backend/trained_models/error_classifier/error_classifier.joblib
backend/trained_models/nli_model/final_model/
```

## Word Proficiency

This is Katrina/Maria's module.

| Part | Location | Notes |
|---|---|---|
| Frontend screen | `frontend/src/WordProficiency.jsx` | Main Word Proficiency UI |
| Frontend styles | `frontend/src/WordProficiency.css` | Word Proficiency styling |
| Tab wrapper | `frontend/src/WordProficiencyTab.jsx` | Word Proficiency tab entry |
| Frontend API service | `frontend/src/services/wpApi.js` | Calls `/api/system/...` |
| Difficult words bridge | `frontend/src/services/difficultWords.js` | Receives words clicked in Reading |
| Backend app | `backend/system/` | Word Proficiency backend |
| Backend models | `backend/system/models.py` | WordState, WordFeatures, attempts/session models |
| Backend views | `backend/system/views_wp.py` | Word Proficiency API views |
| Backend services | `backend/system/services.py` | Import words and orchestration |
| POS/BERT tagging | `backend/system/bert_tagger.py` | POS tag and embedding analysis |
| Session engine | `backend/system/session_engine.py` | Pronunciation session logic |
| Audio/STT | `backend/system/audio_service.py` | Whisper/Groq/OpenAI audio transcription |
| Recommender | `backend/system/recommender.py` | Selects words for session |
| Classifier | `backend/system/classifier.py` | Augmentation recommendation classifier |
| Word DB | `backend/wp.sqlite3` | Word Proficiency database |

Reading Restructurer to Word Proficiency bridge:

```text
ReadingRestructurer.jsx
-> saveDifficultWord(word)
-> frontend/src/services/difficultWords.js
-> localStorage key: salitayo_difficult_words
-> WordProficiency.jsx reads getDifficultWords()
-> wpImportWords()
-> POST /api/system/words/import/
-> backend/system/views_wp.py
-> backend/system/services.py
-> backend/system/bert_tagger.py
```

## Login / Signup

| Part | Location |
|---|---|
| Login page | `frontend/src/pages/Login.jsx` |
| Signup page | `frontend/src/pages/SignUp.jsx` |
| Email verify page | `frontend/src/pages/VerifyEmail.jsx` |
| Protected route | `frontend/src/components/ProtectedRoute.jsx` |
| Auth API service | `frontend/src/services/authApi.js` |
| Backend profiles app | `backend/profiles/` |

## Important Shared Files

| File | Purpose |
|---|---|
| `frontend/src/App.jsx` | Main frontend routing/tabs |
| `frontend/src/main.jsx` | React app entry |
| `frontend/src/styles.css` | Shared frontend styles |
| `backend/salitayo/urls.py` | Main backend route registration |
| `backend/salitayo/settings.py` | Django settings |
| `backend/salitayo/db_router.py` | Routes Word Proficiency DB models |

## Do Not Confuse These

| Folder/File | Meaning |
|---|---|
| `backend/restructurer/` | Reading Restructurer backend |
| `backend/restructurer_inference.py` | Reading Restructurer model inference |
| `backend/assistive_writing_coach/` | Writing Assistant backend |
| `backend/system/` | Word Proficiency backend |
| `frontend/src/ReadingRestructurer.jsx` | Reading Restructurer screen |
| `frontend/src/WritingAssistant.jsx` | Writing Assistant screen |
| `frontend/src/WordProficiency.jsx` | Word Proficiency screen |
| `backend/trained_models/` | Writing Assistant models |
| `backend/models/` | Reading Restructurer models |

## Suggested Cleanup Rule

Do not delete teammate folders. If you need to clean generated files, only clean obvious temporary files such as:

```text
__pycache__/
*.pyc
backend/runserver-*.log
frontend/dist/
outputs/ temporary test exports
```

Keep source folders and model folders intact.
