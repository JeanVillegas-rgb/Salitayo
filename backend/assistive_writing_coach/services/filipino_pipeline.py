"""
Filipino/Tagalog spelling analysis via Groq (llama-3.3-70b-versatile).

Triggered when langdetect identifies the input as Tagalog ('tl').
Returns the same error dict shape as pipeline.py so the frontend and
serializers need zero changes.
"""
import os
import re
import json
import time
import logging

logger = logging.getLogger(__name__)

_groq_client = None

_ERROR_LABELS = {
    "phonetic_sub": "Phonetic Substitution",
    "reversal": "Letter Reversal",
    "omission": "Letter Omission",
    "insertion": "Letter Insertion",
    "transposition": "Letter Transposition",
    "language_mix": "Language Mix",
}

_PROMPT_FILIPINO = """\
Ikaw ay isang spelling error detector para sa mga mag-aaral na may dyslexia na sumusulat sa Filipino o Tagalog.

Suriin ang teksto sa ibaba para sa mga spelling error sa Filipino/Tagalog na mga salita lamang.
HUWAG i-flag ang: mga salitang Ingles sa Taglish na teksto, mga pangalan ng tao/lugar, mga acronym, mga numero.

Para sa bawat maling nae-spell na salita, tukuyin ang uri ng error:
- phonetic_sub: pinalit ang isang letra ng isa na magkaparehong tunog
- reversal: isa o higit pang letra ang nasulat nang baligtad
- omission: may kulang na letra
- insertion: may dagdag na letra
- transposition: dalawang magkaratig na letra ang napalit ng posisyon

Ibalik LAMANG ang isang valid na JSON array. Kung walang errors, ibalik ang [].
Ang bawat item ay dapat may eksaktong mga field na ito:
{
  "word": "ang maling nae-spell na salita exactly as written sa teksto",
  "correction": "tamang Filipino spelling",
  "error_type": "phonetic_sub o reversal o omission o insertion o transposition",
  "error_type_confidence": 0.85,
  "candidates": ["correction", "alternative1", "alternative2"],
  "feedback": "Maikling paliwanag ng error sa Filipino."
}

Walang markdown. Walang paliwanag. JSON array lamang.

Teksto: "{text}"
"""

_PROMPT_TAGLISH_TO_FILIPINO = """\
Ikaw ay isang Filipino writing assistant para sa mga dyslexic na mag-aaral na sumusulat ng Taglish.

Ang teksto sa ibaba ay halo ng Filipino at English. I-convert ito sa purong Filipino sa pamamagitan ng:
1. Pagpapalit ng bawat salitang Ingles ng tamang katumbas nito sa Filipino
2. Pagtama ng mga maling spelling ng Filipino na mga salita

MAHALAGA: Kung ang dalawa o higit pang magkarugtong na salita ay bumubuo ng isang kahulugan, ibalik ang buong parirala bilang ISANG entry lamang.
Halimbawa: "in the" → isang entry na may word="in the", hindi dalawang hiwalay na entry.
Para sa Filipino: "para sa", "sa araw", atbp. — ibalik bilang isang entry.

Para sa bawat salita o pariralang kailangang baguhin, magbalik ng isang JSON object.
HUWAG ibalik ang mga salitang tama na sa Filipino.

Ang bawat object ay dapat may eksaktong mga field na ito:
{
  "word": "ang orihinal na salita o parirala exactly as written sa teksto",
  "correction": "ang tamang Filipino na katumbas",
  "error_type": "language_mix para sa English words, o phonetic_sub/reversal/omission/insertion/transposition para sa spelling errors",
  "error_type_confidence": 0.9,
  "candidates": ["correction", "alternative1"],
  "feedback": "Maikling paliwanag ng pagbabago sa Filipino."
}

Ibalik LAMANG ang valid JSON array. Kung purong Filipino na ang teksto, ibalik ang [].
Walang markdown. Walang paliwanag. JSON array lamang.

Teksto: "{text}"
"""

_PROMPT_TAGLISH_TO_ENGLISH = """\
You are an English writing assistant for Filipino dyslexic learners writing in Taglish.

The text below mixes Filipino and English words. Convert it to pure English by:
1. Replacing every Filipino/Tagalog word with its correct English equivalent
2. Fixing any misspelled English words

IMPORTANT: If two or more consecutive words together form a single meaning, return the entire phrase as ONE entry.
Example: Filipino "para sa" means "for" — return one entry with word="para sa", NOT two separate entries for "para" and "sa".
Other common multi-word Filipino phrases: "sa araw", "ng mga", "sa aking", etc. — always treat as one unit.

For each word or phrase that needs to change, return one JSON object.
Do NOT return words or phrases that are already correct English.

Each object must have exactly these fields:
{
  "word": "the original word or phrase exactly as written in the text",
  "correction": "the correct English equivalent",
  "error_type": "language_mix for Filipino words, or phonetic_sub/reversal/omission/insertion/transposition for spelling errors",
  "error_type_confidence": 0.9,
  "candidates": ["correction", "alternative1"],
  "feedback": "One short sentence explaining the change."
}

Return ONLY a valid JSON array. Empty array [] if the text is already pure English.
No markdown. No explanation. JSON array only.

Text: "{text}"
"""


def _get_client():
    global _groq_client
    if _groq_client is None:
        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to your environment variables."
            )
        from groq import Groq
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _parse_response(content: str) -> list:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
        content = content.rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        logger.warning(f"[FILIPINO] JSON parse failed: {content[:200]}")
        return []


def _compute_positions(text: str, raw_errors: list) -> list:
    """Find each flagged word's character position in the original text."""
    used_spans: set = set()
    result = []
    for err in raw_errors:
        word = err.get("word", "")
        if not word:
            continue
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if span not in used_spans:
                used_spans.add(span)
                result.append({
                    "word": word,
                    "start": m.start(),
                    "end": m.end(),
                    "error_type": err.get("error_type", "phonetic_sub"),
                    "error_type_label": _ERROR_LABELS.get(
                        err.get("error_type", ""), "Spelling Error"
                    ),
                    "error_type_confidence": float(
                        err.get("error_type_confidence", 0.7)
                    ),
                    "correction": err.get("correction", word),
                    "candidates": err.get("candidates", [err.get("correction", word)]),
                    "feedback": err.get("feedback", "Posibleng may error sa baybay."),
                })
                break
    return sorted(result, key=lambda e: e["start"])


def _run_groq(text: str, prompt_template: str, language_key: str) -> dict:
    """Shared Groq runner used by all three Filipino-side pipelines."""
    start_ms = time.time()

    logger.debug("=" * 60)
    logger.debug(f"[{language_key.upper()}] Input: {repr(text)}")

    errors = []
    try:
        client = _get_client()
        prompt = prompt_template.replace('"{text}"', f'"{text}"')

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
        )
        content = resp.choices[0].message.content
        logger.debug(f"[{language_key.upper()}] Groq raw response: {content[:300]}")

        raw_errors = _parse_response(content)
        errors = _compute_positions(text, raw_errors)
        logger.debug(f"[{language_key.upper()}] {len(raw_errors)} raw → {len(errors)} positioned")

    except Exception as e:
        logger.error(f"[{language_key.upper()}] Pipeline error: {e}")
        errors = []

    corrected = text
    offset = 0
    for err in errors:
        adj_start = err["start"] + offset
        adj_end = err["end"] + offset
        best = err["correction"]
        corrected = corrected[:adj_start] + best + corrected[adj_end:]
        offset += len(best) - (err["end"] - err["start"])

    word_count = len(re.findall(r"[A-Za-zÀ-ɏ]+", text))
    elapsed_ms = round((time.time() - start_ms) * 1000)

    logger.debug(f"[{language_key.upper()}] Done: {len(errors)} error(s) | {elapsed_ms}ms")
    logger.debug("=" * 60)

    return {
        "original_text": text,
        "corrected_text": corrected,
        "word_count": word_count,
        "error_count": len(errors),
        "errors": errors,
        "processing_time_ms": elapsed_ms,
        "language": language_key,
    }


def analyze_filipino(text: str) -> dict:
    return _run_groq(text, _PROMPT_FILIPINO, "filipino")


def analyze_taglish_to_filipino(text: str) -> dict:
    return _run_groq(text, _PROMPT_TAGLISH_TO_FILIPINO, "taglish_to_filipino")


def analyze_taglish_to_english(text: str) -> dict:
    return _run_groq(text, _PROMPT_TAGLISH_TO_ENGLISH, "taglish_to_english")
