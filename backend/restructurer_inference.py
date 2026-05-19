"""
restructurer_inference.py - Dyslexia-Friendly Text Restructurer
Routes English and Tagalog requests to separate local seq2seq models when
available, while keeping the existing English model untouched.
"""

from __future__ import annotations

import os
import re
import logging
import json
from pathlib import Path
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model path resolution and loading
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables manually from .env if present
env_path = BASE_DIR / ".env"
if env_path.is_file():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _is_usable_model_dir(path: Path | None) -> bool:
    if not path or not path.is_dir():
        return False
    has_config = (path / "config.json").is_file()

    # Accept a variety of common model weight files:
    # - single-file safetensors (*.safetensors)
    # - single-file PyTorch bin (pytorch_model.bin)
    # - sharded PyTorch files (pytorch_model-00001-of-00002, index json)
    # - Flax checkpoint (flax_model.msgpack)
    has_weights = False
    if (path / "model.safetensors").is_file() or (path / "pytorch_model.bin").is_file():
        has_weights = True
    else:
        for p in path.iterdir():
            if not p.is_file():
                continue
            name = p.name.lower()
            if name.endswith(".safetensors"):
                has_weights = True
                break
            if name.startswith("pytorch_model"):
                has_weights = True
                break
            if name == "pytorch_model.bin.index.json":
                has_weights = True
                break
            if name == "flax_model.msgpack":
                has_weights = True
                break

    return has_config and has_weights


def _resolve_model_dir(kind: str = "default") -> Path | None:
    if kind == "tagalog":
        env_path = os.getenv("TAGALOG_RESTRUCTURER_MODEL_DIR", "").strip()
        candidates = [
            BASE_DIR / "models" / "tagalog_restructurer",
            BASE_DIR / "models" / "mt5_tagalog_restructurer",
            BASE_DIR / "models" / "salitayo_tagalog_restructurer",
            BASE_DIR / "models" / "salitayo_tagalog_v3_candidate_model",
            BASE_DIR / "models" / "tagalog_open_topic_restructurer",
        ]
    else:
        env_path = os.getenv("RESTRUCTURER_MODEL_DIR", "").strip()
        candidates = [
            BASE_DIR / "models" / "t5_restructurer_updated",
            BASE_DIR / "models" / "t5_restructurer",
        ]

    if env_path:
        path = Path(env_path).expanduser().resolve()
        if _is_usable_model_dir(path):
            return path

    for path in candidates:
        if _is_usable_model_dir(path):
            return path

    if kind == "tagalog":
        return None

    raise FileNotFoundError(
        "English model not found. Expected it at backend/models/t5_restructurer."
    )


DEFAULT_MODEL_DIR = _resolve_model_dir("default")
TAGALOG_MODEL_DIR = _resolve_model_dir("tagalog")
MODEL_CACHE: dict[str, tuple[AutoTokenizer, AutoModelForSeq2SeqLM, Path]] = {}


def _load_model(model_dir: Path, cache_key: str):
    if cache_key in MODEL_CACHE:
        cached_tokenizer, cached_model, cached_dir = MODEL_CACHE[cache_key]
        if cached_dir == model_dir:
            return MODEL_CACHE[cache_key]
        else:
            print(f"[restructurer_inference] Path changed from {cached_dir} to {model_dir}. Reloading model cache...")

    print(f"[SUCCESS] LOADING {cache_key.upper()} MODEL FROM: {model_dir}")
    try:
        if cache_key == "default":
            # Bypass the Hugging Face local config serialization bug on newer Python versions
            # by loading the clean, standard T5 tokenizer.
            from transformers import T5TokenizerFast
            tokenizer = T5TokenizerFast.from_pretrained("t5-small")
        else:
            use_fast_flag = False if cache_key == "tagalog" else True
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir),
                use_fast=use_fast_flag,
                local_files_only=True,
                trust_remote_code=False,
            )
    except Exception as exc:
        print(f"[WARN] Preferred tokenizer load failed for {cache_key}: {exc}. Trying fallback...")
        try:
            tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir),
                use_fast=True,
                local_files_only=True,
                trust_remote_code=False,
            )
        except Exception as exc2:
            print(f"[WARN] Fallback tokenizer load failed: {exc2}. Trying standard T5 tokenizer...")
            from transformers import T5TokenizerFast
            tokenizer = T5TokenizerFast.from_pretrained("t5-small")

    model = AutoModelForSeq2SeqLM.from_pretrained(str(model_dir), local_files_only=True, ignore_mismatched_sizes=True).to(DEVICE)
    model.eval()
    MODEL_CACHE[cache_key] = (tokenizer, model, model_dir)
    print(f"[restructurer_inference] {cache_key} model ready.")
    return MODEL_CACHE[cache_key]


def _is_tagalog_lang(lang: str) -> bool:
    return str(lang or "").lower().strip() in {"tl", "tagalog", "fil", "filipino"}


def _select_model(lang: str):
    global TAGALOG_MODEL_DIR
    if _is_tagalog_lang(lang) and TAGALOG_MODEL_DIR:
        return (*_load_model(TAGALOG_MODEL_DIR, "tagalog"), "tagalog")
    if _is_tagalog_lang(lang):
        TAGALOG_MODEL_DIR = _resolve_model_dir("tagalog")
        if TAGALOG_MODEL_DIR:
            print(f"[restructurer_inference] Tagalog model detected at request time: {TAGALOG_MODEL_DIR}")
            return (*_load_model(TAGALOG_MODEL_DIR, "tagalog"), "tagalog")
    
    # Dynamically resolve default model dir at request time
    default_dir = _resolve_model_dir("default")
    return (*_load_model(default_dir, "default"), "default")


# Lazy-load module attributes on demand to prevent memory mapping at startup
def __getattr__(name):
    if name in {"TOKENIZER", "MODEL", "MODEL_DIR"}:
        tokenizer, model, model_dir = _load_model(DEFAULT_MODEL_DIR, "default")
        globals()["TOKENIZER"] = tokenizer
        globals()["MODEL"] = model
        globals()["MODEL_DIR"] = model_dir
        return globals()[name]
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

if TAGALOG_MODEL_DIR:
    print(f"[restructurer_inference] Tagalog model detected at: {TAGALOG_MODEL_DIR}")
else:
    print("[restructurer_inference] No Tagalog model folder detected yet. Expected: backend/models/tagalog_restructurer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_INPUT_CHARS = 30
MAX_CHUNK_CHARS = 300
MAX_NEW_TOKENS = 128
DEFAULT_BEAMS = 4

_SENTINEL_RE = re.compile(r"<extra_id_\d+>")

# ---------------------------------------------------------------------------
# Prompt builder - Supports existing English and Tagalog fine-tune prefixes
# ---------------------------------------------------------------------------
def build_prompt(lang: str, text: str, protected_terms: list | None = None) -> str:
    lang = (lang or "en").lower()
    text = (text or "").strip()

    if lang in ["en", "english"]:
        prompt = f"restructure: {text}"
    else:
        l_code = "fil" if _is_tagalog_lang(lang) else lang
        prompt = f"restructure {l_code}: {text}"

    if protected_terms:
        terms = ", ".join(t.strip() for t in protected_terms if str(t).strip())
        if terms:
            prompt += f" (Keep: {terms})"
    return prompt


# ---------------------------------------------------------------------------
# Post-processing and formatting
# ---------------------------------------------------------------------------
def format_as_bullets(text: str) -> str:
    """Break simplified English text into clear, readable bullet points."""
    text = (text or "").strip()
    if not text:
        return ""
    # Strip any existing leading bullet points, dashes, stars, or dots from the sentences
    text = re.sub(r"^[\s\-•\*]+", "", text, flags=re.MULTILINE)
    
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]

    lines = []
    for part in parts:
        part_clean = re.sub(r"^[\s\-•\*]+", "", part).strip()
        if not part_clean:
            continue
        if not part_clean.endswith((".", "!", "?")):
            part_clean += "."
        lines.append(f"- {part_clean}")
    return " ".join(lines)


def _english_rule_simplify(text: str, protected_terms: list | None = None) -> str:
    """Deterministic lexical simplifier and passive-to-active rewriter for English."""
    text = (text or "").strip()
    if not text:
        return ""

    protected = set()
    if protected_terms:
        for t in protected_terms:
            if t:
                protected.add(t.strip().lower())

    # 1. Passive-to-active voice transformation
    # Handles "(was/were/is/are) [verb]ed by [agent]" -> "[agent] [active_verb] [object]"
    def _passive_to_active(sentence: str) -> str:
        sentence = sentence.strip()
        if not sentence:
            return sentence

        end = ""
        if sentence[-1:] in ".!?":
            end = sentence[-1]
            sentence = sentence[:-1].strip()

        # Split sentence into sub-clauses by common subclause conjunctions and punctuation to prevent greedy matching
        clause_parts = re.split(r"(\b(?:when|if|because|although|that|and|but|or)\b|[,;])", sentence, flags=re.I)
        
        rewritten_parts = []
        for part in clause_parts:
            part_str = part.strip()
            if not part_str:
                rewritten_parts.append(part)
                continue
                
            # Match only local clause passive voice
            # The object is now limited to words within the clause, preventing cross-clause bleeding
            preps = r"about|above|across|after|against|along|among|around|at|before|behind|below|beneath|beside|between|by|during|for|from|in|inside|into|near|of|off|on|onto|outside|over|past|through|to|under|underneath|until|up|upon|with|within|without"
            pattern = (
                r"\b(?P<object>[a-zA-Z\s'\-]+?)\s+(?:was|were|is|are|be)\s+(?:(?P<adverb>[a-z]+ly)\s+)?(?P<verb>[a-z]+ed)\s+(?P<prep>(?:(?:(?:" + preps + r")\s+[a-zA-Z\s'\-]+?)+)?)\s*by\s+(?P<agent>[a-zA-Z\s'\-]+)(?:\b|$)"
            )
            match = re.search(pattern, part_str, flags=re.IGNORECASE)
            if not match:
                rewritten_parts.append(part)
                continue

            obj = match.group("object").strip()
            verb = match.group("verb").strip()
            agent = match.group("agent").strip()
            adverb = (match.group("adverb") or "").strip()
            prep = (match.group("prep") or "").strip()
            if not obj or not agent:
                rewritten_parts.append(part)
                continue

            # Verify neither is protected
            if agent.lower() in protected or obj.lower() in protected:
                rewritten_parts.append(part)
                continue

            # Convert verb tense (best-effort active form)
            active_verb = verb
            matched_segment = match.group(0).lower()
            if "is" in matched_segment or "are" in matched_segment or "be" in matched_segment or "was" in matched_segment or "were" in matched_segment:
                if active_verb.endswith("ed"):
                    if active_verb.endswith(("ted", "sed", "med", "ged", "ded", "zed", "ved", "red")):
                        active_verb = active_verb[:-1]  # slice only 'd', leaving 'e'
                    else:
                        active_verb = active_verb[:-2]  # slice 'ed'
                is_plural = agent.lower().endswith("s") and not agent.lower().endswith("ss")
                if ("is" in matched_segment or "are" in matched_segment or "be" in matched_segment) and not is_plural:
                    if not active_verb.endswith("s") and not active_verb.endswith("es"):
                        active_verb += "s"

            # Reconstruct the clause
            verb_phrase = f"{adverb} {active_verb}".strip()
            prep_phrase = f" {prep}".rstrip() if prep else ""
            rewritten_clause = f"{agent} {verb_phrase} {obj}{prep_phrase}"
            
            # Replace only the matched segment in the part, preserving surrounding words
            new_part = part_str.replace(match.group(0), rewritten_clause)
            
            # Restore leading/trailing spacing from original part
            leading_space = part[:len(part) - len(part.lstrip())]
            trailing_space = part[len(part.rstrip()):]
            rewritten_parts.append(f"{leading_space}{new_part}{trailing_space}")

        res = "".join(rewritten_parts)
        return f"{res}{end}" if end else res

    # Process passive voice sentence by sentence
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    text = " ".join(_passive_to_active(s) for s in sentences)

    # 2. Dynamic, Open-Topic Synonyms Layer: loads from synonyms.json in the background
    synonyms = {}
    synonyms_path = Path(__file__).resolve().parent / "synonyms.json"
    
    # Auto-create synonyms.json with robust academic/lexical pairs if not exists or is empty
    if not synonyms_path.exists() or synonyms_path.stat().st_size == 0:
        default_synonyms = {
            "biodiversity": "variety of life",
            "severely degraded": "badly damaged",
            "degraded": "damaged",
            "compromised": "damaged",
            "heavily disrupted": "greatly upset",
            "disrupted": "upset",
            "ignored": "neglected",
            "utilize": "use",
            "frequently": "often",
            "demonstrated": "showed",
            "implementation": "start"
        }
        try:
            with open(synonyms_path, "w", encoding="utf-8") as f:
                json.dump(default_synonyms, f, indent=4)
        except Exception:
            pass

    try:
        if synonyms_path.exists():
            with open(synonyms_path, "r", encoding="utf-8") as f:
                synonyms = json.load(f)
    except Exception:
        pass

    for key, replacement in synonyms.items():
        if key.strip().lower() in protected:
            continue
            
        pattern = rf"\b{re.escape(key)}\b"
        
        def replace_case(match):
            val = match.group(0)
            if val.istitle():
                return replacement.title()
            if val.isupper():
                return replacement.upper()
            return replacement

        text = re.sub(pattern, replace_case, text, flags=re.I)

    return text


def clean_generated_text(text: str, lang: str = "en", protected_terms: list | None = None) -> str:
    """Remove unwanted tokens and artifacts."""
    text = _SENTINEL_RE.sub("", text or "")
    text = re.sub(r"^\s*(paraphrase|simplify|restructure\s+\w+)\s*:\s*", "", text, flags=re.I)

    for marker in ["IMPORTANT:", "Note:", "Keep these words"]:
        idx = text.lower().find(marker.lower())
        if idx != -1:
            text = text[:idx]

    cleaned = re.sub(r"\s+", " ", text).strip()
    if _is_tagalog_lang(lang):
        return cleaned
    # Remove any stray meta-sentences the model sometimes includes, e.g. "rewriting in active voice"
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", cleaned) if p.strip()]
    filtered = []
    meta_patterns = re.compile(r"\b(active voice|rewrit|paraphras|simplif|simpler|keep these words|keep:?)\b", flags=re.I)
    for part in parts:
        if meta_patterns.search(part):
            continue
        filtered.append(part)

    cleaned = " ".join(filtered)
    return format_as_bullets(cleaned)


def deterministic_restructure(text: str, lang: str = "en", protected_terms: list | None = None) -> str:
    """Fallback used after the local model fails."""
    text = (text or "").strip()
    if _is_tagalog_lang(lang):
        return text
    return format_as_bullets(text)


# ---------------------------------------------------------------------------
# Fallback decision
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (text or "").lower())).strip()


def _should_fallback(original: str, cleaned: str, raw: str) -> bool:
    if not cleaned:
        return True
    if _SENTINEL_RE.search(raw or ""):
        return True
    if _normalize(cleaned) == _normalize(original):
        return True
    if len(re.findall(r"\b\w+\b", cleaned)) < 3:
        return True
    return False


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
def _validate_input(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Please enter some text."}
    if len(text) < MIN_INPUT_CHARS:
        return {"ok": False, "error": f"Text is too short. Try at least {MIN_INPUT_CHARS} characters."}
    return {"ok": True}


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def _split_into_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long text into smaller chunks for the model to process."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return [text]

    chunks, current = [], ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(sentence)
            continue

        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = sentence

    if current:
        chunks.append(current)
    return chunks


# ---------------------------------------------------------------------------
# Single-chunk inference
# ---------------------------------------------------------------------------
def _predict_chunk(
    text: str,
    lang: str,
    protected_terms: list | None,
    max_new_tokens: int,
    num_beams: int,
) -> tuple[str, str]:
    tokenizer, model, _model_dir, model_key = _select_model(lang)
    
    current_text = text
    max_passes = 1 if lang in ["en", "english"] else 3
    
    for pass_idx in range(max_passes):
        prompt = build_prompt(lang, current_text, protected_terms)
        
        # T5 512-token limit check
        num_tokens = tokenizer(prompt, return_tensors="pt")["input_ids"].shape[1]
        if num_tokens > 512:
            if pass_idx == 0:
                print(f"[WARNING] Input text length ({num_tokens} tokens) exceeds T5's limit of 512. Truncating to fit.")
            
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(DEVICE)

        with torch.no_grad():
            generated = model.generate(
                **inputs,
                max_length=256,
                num_beams=4,
                no_repeat_ngram_size=3,
                repetition_penalty=2.0,
                early_stopping=True,
            )

        raw = tokenizer.decode(generated[0], skip_special_tokens=False)
        # Debug: show which model is selected
        logger.debug(f"[DEBUG] Using model_key='{model_key}' for language='{lang}'")
        # Debug: tokenization length
        token_len = tokenizer(prompt, return_tensors="pt")["input_ids"].shape[1]
        logger.debug(f"[DEBUG] Prompt token length={token_len}")
        # Debug: raw model output (truncated)
        logger.debug(f"[DEBUG] Raw generation output: {raw[:200]}")
        cleaned = clean_generated_text(tokenizer.decode(generated[0], skip_special_tokens=True), lang, protected_terms)

        # French translation hallucination guard
        if lang in ["en", "english"] and re.search(r"\b(les|des|dans|pour|est|une|qui|que|avec|sur|dans|mais|sont)\b", cleaned.lower()):
            logger.warning(f"[WARNING] French translation detected: '{cleaned}'. Retrying with target language directive...")
            inputs = tokenizer(f"restructure in english: {current_text}", return_tensors="pt", truncation=True, max_length=512).to(DEVICE)
            with torch.no_grad():
                generated = model.generate(
                    **inputs,
                    max_length=256,
                    num_beams=4,
                    no_repeat_ngram_size=3,
                    repetition_penalty=2.0,
                    early_stopping=True,
                )
            cleaned = clean_generated_text(tokenizer.decode(generated[0], skip_special_tokens=True), lang, protected_terms)

        # Apply deterministic refinement layer to ensure comprehensive simplification
        if lang in ["en", "english"]:
            cleaned_stripped = re.sub(r"^[\s\-•\*]+", "", cleaned).strip()
            simplified = _english_rule_simplify(cleaned_stripped, protected_terms)
            cleaned = format_as_bullets(simplified)

        # Strip out intermediate bullet point dashes to pass a clean sentence to the next iteration
        cleaned_clean = re.sub(r"^-\s*", "", cleaned).strip()

        # If the text has stopped changing, or if it fell back to original, terminate the passes
        if cleaned_clean.lower() == current_text.lower() or _should_fallback(current_text, cleaned, raw):
            break
            
        current_text = cleaned_clean

    # Re-apply dyslexia-friendly bullets at the very end if it's English
    final_output = current_text
    if lang in ["en", "english"] and not final_output.startswith("-"):
        final_output = format_as_bullets(final_output)

    # Clean up any potential double-bullets or leading dashes
    final_output = re.sub(r"^[\s\-•\*]+", "- ", final_output).strip()

    return final_output, model_key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def predict(
    text: str,
    lang: str = "en",
    protected_terms: list | None = None,
    max_new_tokens: int = MAX_NEW_TOKENS,
    num_beams: int = DEFAULT_BEAMS,
) -> dict:
    """
    Restructure text with the local model selected by language.

    Returns:
        {"raw": str, "cleaned": str, "model_key": str} on success
        {"raw": "", "cleaned": "", "error": str} on validation failure
    """
    text = (text or "").strip()
    check = _validate_input(text)
    if not check["ok"]:
        return {"raw": "", "cleaned": check["error"], "error": check["error"], "model_key": "none"}

    # Split the input text into distinct sentences to match the T5 fine-tuning single-sentence training format
    # This prevents the model from dropping or skipping sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    
    results = []
    model_keys = set()
    
    for sentence in sentences:
        if len(sentence) < MIN_INPUT_CHARS:
            # Keep very short fragments or punctuation as is
            results.append(sentence)
        else:
            cleaned, model_key = _predict_chunk(sentence, lang, protected_terms, max_new_tokens, num_beams)
            
            # Apply copy-guard logic per sentence
            stripped_input = re.sub(r"^\s*-\s*", "", sentence).strip().lower()
            stripped_clean = re.sub(r"^\s*-\s*", "", cleaned).strip().lower()
            if stripped_clean == stripped_input:
                logger.debug(f"[DEBUG] Output identical to input for sentence '{sentence}' – retrying with higher beam count")
                cleaned, model_key = _predict_chunk(sentence, lang, protected_terms, max_new_tokens, num_beams=8)
                
            results.append(cleaned)
            model_keys.add(model_key)

    # Combine all simplified sentence results into a formatted bulleted list
    combined = " ".join(result for result in results if result)
    
    # Make sure we clean and properly bullet point the combined output
    if lang in ["en", "english"]:
        # Strip existing leading bullets/whitespace to re-bullet cleanly
        combined = re.sub(r"^[\s\-•\*]+", "", combined, flags=re.MULTILINE)
        combined = format_as_bullets(combined)
        
    model_key = "tagalog" if "tagalog" in model_keys else "default"
    return {"raw": combined, "cleaned": combined, "model_key": model_key}
