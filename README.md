# SALITAyo Restructurer

Minimal Django REST + React scaffold for a dyslexia-friendly academic text restructurer.

## Setup

1. Copy `backend/.env.example` to `backend/.env` and fill in values if you want Anthropic support.
2. Copy `frontend/.env.example` to `frontend/.env` if you want to override the API base URL.

## Backend

```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py runserver
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Test

```bash
cd backend
python -m compileall .
python manage.py test
```

## API

`POST /api/restructure/`

```json
{
  "input_text": "The samples were analyzed by the researchers.",
  "source_context": "reading simplification"
}
```

You can also send `input_file` as a UTF-8 `.txt` file with `multipart/form-data`.

### Response shape

```json
{
  "success": true,
  "input_text": "...",
  "restructured_text": "...",
  "chunks": [
    {
      "chunk_id": "chunk-1",
      "text": "...",
      "highlight_terms": ["SALITAyo"],
      "color_terms": ["SALITAyo"]
    }
  ],
  "metadata": {
    "font_family": "OpenDyslexic, Atkinson Hyperlegible, sans-serif",
    "layout": "sentence-per-line",
    "bilingual_awareness": true,
    "rag_guidance": [],
    "preserved_terms": ["SALITAyo"]
  }
}
```
