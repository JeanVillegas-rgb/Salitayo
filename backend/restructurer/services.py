from __future__ import annotations

import json
import logging
import os
import re
import time
from difflib import SequenceMatcher
try:
    import requests
except Exception:
    requests = None

# Optional NLP imports — make missing heavy deps non-fatal for manage.py commands
try:
    import spacy
except Exception:
    spacy = None
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from .corpus import RagCorpus
from .ner import BertNERProtector
from .evaluation import SimplificationEvaluator
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(dotenv_path=None, override=True):
        if not dotenv_path or not os.path.exists(dotenv_path):
            return
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if override or key not in os.environ:
                        os.environ[key] = val

logger = logging.getLogger(__name__)

# Load environment variables from absolute path to prevent folder-mismatch
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)
logger.info("Loading .env from: %s", env_path)

if not os.getenv("GROQ_API_KEY"):
    logger.error("CRITICAL: GROQ_API_KEY NOT FOUND IN ENV AT %s", env_path)
else:
    logger.info("GROQ_API_KEY successfully loaded.")

# =============================================================================
# LOCAL MODEL LOADING AT MODULE INIT TIME (fail fast, not at request time)
# =============================================================================
local_inference_module = None
local_model_error = None


def _load_local_inference_module():
    """Lazy-load local inference to recover after runtime fixes."""
    global local_inference_module, local_model_error
    if local_inference_module and hasattr(local_inference_module, "predict"):
        return local_inference_module

    try:
        local_inference_path = Path(__file__).resolve().parent.parent / "restructurer_inference.py"
        if not local_inference_path.exists():
            local_model_error = f"restructurer_inference.py not found at {local_inference_path}"
            logger.error("[SALITAyo] %s", local_model_error)
            local_inference_module = None
            return None

        import importlib.util
        spec = importlib.util.spec_from_file_location("local_inference", str(local_inference_path))
        local_inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(local_inference_module)
        local_model_error = None
        logger.info("[SALITAyo] Local inference module loaded on demand")
        return local_inference_module
    except Exception as exc:
        import traceback
        err_msg = traceback.format_exc()
        with open("local_model_error.log", "w", encoding="utf-8") as f:
            f.write(err_msg)
        print("\n" + "="*80 + "\nLOCAL MODEL LOADING ERROR:\n" + err_msg + "="*80 + "\n")
        local_model_error = f"Failed to load local inference module: {str(exc)}"
        logger.error("[SALITAyo] %s", local_model_error)
        local_inference_module = None
        return None

try:
    local_inference_path = Path(__file__).resolve().parent.parent / "restructurer_inference.py"
    if local_inference_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("local_inference", str(local_inference_path))
        local_inference_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(local_inference_module)
        logger.info("[SALITAyo] Local mT5 model loaded successfully at startup")
    else:
        local_model_error = f"restructurer_inference.py not found at {local_inference_path}"
        logger.error("[SALITAyo] %s", local_model_error)
except Exception as e:
    local_model_error = f"Failed to load local inference module: {str(e)}"
    logger.error("[SALITAyo] %s", local_model_error)


SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
CLAUSE_SPLIT_PATTERN = re.compile(r"\s*(?:;|:\s+|,\s+(?:and|but|while|because|which|that|upang|dahil|sapagkat)\s+)+\s*", re.IGNORECASE)

LEADING_DISCOURSE_MARKERS = (
    "however",
    "therefore",
    "moreover",
    "furthermore",
    "additionally",
    "meanwhile",
    "otherwise",
    "instead",
    "then",
    "thus",
    "also",
    "because",
    "when",
    "while",
    "since",
    "although",
    "though",
    "after",
    "before",
    "during",
    "it",
    "this",
    "that",
    "these",
    "those",
    "there",
    "here",
    "notwithstanding",
)

NON_PRESERVED_CAPITALIZED_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "but",
    "or",
    "nor",
    "for",
    "so",
    "yet",
    "to",
    "of",
    "in",
    "on",
    "at",
    "by",
    "from",
    "with",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "this",
    "that",
    "these",
    "those",
    "he",
    "she",
    "they",
    "we",
    "you",
    "i",
    "kailangan",
    "mga",
    "ang",
    "ng",
    "sa",
    "si",
    "ni",
    "kay",
    "ito",
    "iyan",
    "iyon",
    "dito",
    "diyan",
    "doon",
}

COMMON_ACADEMIC_VERBS = (
    "show",
    "shows",
    "showed",
    "found",
    "find",
    "finds",
    "support",
    "supports",
    "supported",
    "reveal",
    "reveals",
    "revealed",
    "indicate",
    "indicates",
    "indicated",
    "suggest",
    "suggests",
    "suggested",
    "cause",
    "causes",
    "caused",
    "improve",
    "improves",
    "improved",
    "reduce",
    "reduces",
    "reduced",
    "increase",
    "increases",
    "increased",
    "help",
    "helps",
    "helped",
    "use",
    "uses",
    "used",
    "provide",
    "provides",
    "provided",
    "affect",
    "affects",
    "affected",
    "study",
    "studies",
    "studied",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "ensure",
    "ensures",
    "ensured",
    "resulted",
    "occur",
    "occurs",
    "occurred",
    "achieve",
    "achieves",
    "achieved",
    "challenge",
    "challenges",
    "challenged",
    "necessitate",
    "necessitates",
    "necessitated",
    "require",
    "requires",
    "required",
    "perform",
    "performs",
    "performed",
    "observe",
    "observes",
    "observed",
    "identify",
    "identifies",
    "identified",
    "establish",
    "establishes",
    "established",
    "describe",
    "describes",
    "described",
    "explain",
    "explains",
    "explained",
    "develop",
    "develops",
    "developed",
    "apply",
    "applies",
    "applied",
    "include",
    "includes",
    "included",
)


@dataclass
class RestructuredChunk:
    chunk_id: str
    text: str
    highlight_terms: list[str]


class ReadingRestructurerService:
    def __init__(self, corpus: RagCorpus | None = None):
        corpus_dir = Path(settings.BASE_DIR) / "rag_corpus"
        self.corpus = corpus or RagCorpus(corpus_dir)
        # Tracks words that were augmented (syllable-chunked) in the last restructure run
        self._last_augmented_words: list[str] = []
        
        # Initialize NER protector, evaluator, and SpaCy
        self.ner_protector = BertNERProtector()
        self.evaluator = SimplificationEvaluator()
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except:
            self.nlp = None
        # Lazy-loaded Gemma/text2text pipeline placeholder
        self._gemma_pipeline = None

    def _detect_language(self, text: str) -> str:
        """Detects if text is primarily Tagalog or English."""
        tl_markers = {"mga", "ng", "ang", "sa", "ay", "na", "si", "at", "ito", "sila", "namin", "nila", "mo", "siya"}
        words = set(re.findall(r"\b\w+\b", text.lower()))
        tl_count = len(words.intersection(tl_markers))
        return "tl" if tl_count > 0 else "en"

    def restructure(
        self,
        text: str,
        source_context: str = "",
        highlight_words: list[str] | None = None,
        target_language: str = "en",
        metrics: dict | None = None,
        mixed_output: str = "taglish",
    ):
        """High-performance restructuring pipeline with adaptive levers."""
        try:
            # 1. ADAPTIVE LEVERS (If-Then Logic from reference)
            m = metrics or {}
            rr = float(m.get("replay_rate", 0))
            toc = float(m.get("toc_ratio", 1.0))
            sdp = float(m.get("sdp_ratio", 1.0))
            vfi = int(m.get("vfi_count", 0))

            # LEVER 1: Chunk Size
            chunk_size = 14
            if rr > 0.6: chunk_size = max(chunk_size - 4, 8)
            
            # LEVER 2: Playback Speed
            playback_speed = 1.0
            if toc > 1.5: playback_speed = max(playback_speed - 0.15, 0.7)
            
            # LEVER 3: Restructuring Aggressiveness
            aggressiveness = "BALANCED"
            if sdp < 0.5: aggressiveness = "AGGRESSIVE"
            
            guidance = self._build_guidance(text, source_context)
            
            # 0. Prep (Augmentation will happen on output, not input)
            self._last_augmented_words = []
            
            # 5. Visual Chunking
            start_time = time.perf_counter()
            adaptive_trace = []
            
            # 1. NER Protection
            ner_start = time.perf_counter()
            ner_protected_terms = self.ner_protector.get_protected_terms(text)
            adaptive_trace.append({"step": "BERT NER Protection", "duration": round(time.perf_counter() - ner_start, 3), "status": "success"})

            # 2. Translation (if needed)
            trans_start = time.perf_counter()
            clean_target = str(target_language or "en").lower().strip()
            if clean_target not in ["en", "tl", "mix", "mixed"]:
                clean_target = "en"
            target_language = clean_target

            preserved_terms = self._extract_preserved_terms(text)
            preserved_terms.extend(ner_protected_terms)
            all_protected = list(set(preserved_terms))
            
            # Only translate anchors if the desired output language is different from the input language
            # OR if the target is Tagalog and the anchor is clearly English (to prevent Taglish)
            input_lang = self._detect_language(text)
            target_name = "Tagalog" if target_language == "tl" else "English"
            
            if all_protected:
                should_translate = (input_lang != target_language)
                
                # Special case: If target is Tagalog, we MUST translate English anchors to ensure purity
                if target_language == "tl":
                    # We'll let the AI decide which ones need translation to reach "Pure Tagalog"
                    all_protected = self._translate_anchor_list(all_protected, target_name)
                    adaptive_trace.append({"step": "Anchor Translation (Tagalog Purity)", "duration": round(time.perf_counter() - trans_start, 3), "status": "success"})
                elif should_translate and target_language not in ["mix", "mixed"]:
                    all_protected = self._translate_anchor_list(all_protected, target_name)
                    adaptive_trace.append({"step": f"Anchor Translation ({target_name})", "duration": round(time.perf_counter() - trans_start, 3), "status": "success"})
                else:
                    adaptive_trace.append({"step": "Anchor Translation", "duration": 0.0, "status": "skipped (same language)"})

            # 3. Simplification (Adaptive Tiering)
            simp_start = time.perf_counter()
            # RAG DISABLED for simplification to ensure it depends SOLELY on input
            simplified_text, mode, simp_trace = self._simplify_text_with_trace(
                text=text,
                source_context=f"AGGR:{aggressiveness}", # Pass aggressiveness to prompt builder
                guidance=[],       # Cleared RAG guidance
                protected_terms=all_protected,
                target_language=target_language,
                mixed_output=mixed_output,
            )
            adaptive_trace.extend(simp_trace)
            adaptive_trace.append({"step": "Total Simplification", "duration": round(time.perf_counter() - simp_start, 3), "mode": mode})

            # 3.5. Restructuring with Local Model (Add Bullet Points & Line Breaks)
            restructure_start = time.perf_counter()
            text_to_restructure = simplified_text or text  # Use simplified text if available, else original
            local_module = None
            if target_language not in ["tl", "tagalog", "fil", "filipino", "mix", "mixed"]:
                local_module = _load_local_inference_module()
            if local_module and hasattr(local_module, "predict"):
                try:
                    restructure_result = local_module.predict(text_to_restructure, target_language, protected_terms=all_protected)
                    restructured = restructure_result.get("cleaned", text_to_restructure)
                    if restructured:
                        text_to_restructure = restructured
                        model_key = restructure_result.get("model_key", "default")
                        local_model_used = True
                        if model_key == "tagalog":
                            mode = "tagalog-restructure"
                        elif target_language == "tl":
                            mode = "tagalog-model-missing-fallback"
                        else:
                            mode = "simplify+restructure"
                        adaptive_trace.append({
                            "step": "Local Model Restructuring",
                            "duration": round(time.perf_counter() - restructure_start, 3),
                            "status": f"success ({model_key})",
                        })
                    else:
                        adaptive_trace.append({"step": "Local Model Restructuring", "duration": round(time.perf_counter() - restructure_start, 3), "status": "skipped (empty output)"})
                except Exception as e:
                    import traceback
                    err_msg = traceback.format_exc()
                    with open("local_model_error.log", "w", encoding="utf-8") as f:
                        f.write(err_msg)
                    print("\n" + "="*80 + "\nLOCAL MODEL RESTRUCTURING ERROR:\n" + err_msg + "="*80 + "\n")
                    adaptive_trace.append({"step": "Local Model Restructuring", "duration": round(time.perf_counter() - restructure_start, 3), "status": f"error: {str(e)}"})
                    logger.warning("Local model restructuring failed, continuing without it: %s", str(e))
            else:
                adaptive_trace.append({"step": "Local Model Restructuring", "duration": 0.0, "status": "skipped (model not available)"})

            # Rely 100% purely on local model output without any static dictionaries, fallback lists, or word-cuts.
            if target_language in ["en", "english"]:
                mode = "local-model"
            adaptive_trace.append(
                {
                    "step": "Near-copy Guard",
                    "duration": 0.0,
                    "status": "fully relied on local model output as requested by user" if target_language in ["en", "english"] else "using API response",
                }
            )

            # 4. Rendering & Purification
            render_start = time.perf_counter()
            chunks = self._build_chunks_from_text(text_to_restructure or text, original_text=text, chunk_size=chunk_size)
            logger.info("DEBUG: AI Simplification Done. Mode: %s, Result Length: %d", mode, len(text_to_restructure or ""))

            # 4. Universal Post-Processing for Augmentation
            rendered_text = text_to_restructure or ""
            final_augmented = set() # Start fresh to only include output words
            
            # (Syllable chunking completely disabled at user request to prevent words from being cut up)
            preserved_terms = list(final_augmented)
            rendered_text = self._normalize_whitespace(rendered_text)
            
            # Final Chunking with Augmented Text
            chunks = self._build_chunks_from_text(rendered_text, original_text=text, preserved_terms=preserved_terms, chunk_size=chunk_size)
        
            # Evaluate simplification quality
            # If model returned empty, apply deterministic lexical fallback before evaluation
            if not text_to_restructure:
                text_to_restructure = self._lexical_simplify(text, all_protected)
                mode = "deterministic-fallback"
                rendered_text = text_to_restructure
                chunks = self._build_chunks_from_text(rendered_text, original_text=text, preserved_terms=preserved_terms, chunk_size=chunk_size)
            evaluation_metrics = self.evaluator.evaluate(text, text_to_restructure)
            # Final Diagnostic Data (Real Observational Metrics)
            total_duration = round(time.perf_counter() - start_time, 3)
            diagnostic_log = {
                "status": "success",
                "mode": mode,
                "total_latency": total_duration,
                "adaptive_trace": adaptive_trace,
                "engine": "SALITAyo-Stable-V2",
                "metrics": {
                    "rr": {"label": "Replay Rate (RR)", "value": f"{rr:.2f}", "status": "STRUGGLE" if rr > 0.6 else "FLUENCY"},
                    "toc": {"label": "Time Ratio (ToC)", "value": f"{toc:.2f}", "status": "STRUGGLE" if toc > 1.5 else "FLUENCY"},
                    "vfi": {"label": "Vocab Friction (VFI)", "value": str(vfi), "status": "STRUGGLE" if vfi > 3 else "FLUENCY"},
                    "sdp": {"label": "Deep Point (SDP)", "value": f"{int(sdp*100)}%", "status": "STRUGGLE" if sdp < 0.5 else "FLUENCY"},
                }
            }
            # --- FINAL BULLETPROOF PURIFIER (Tagalog only) ---
            if target_language == "tl":
                rendered_text = self._bulletproof_purify(rendered_text)
                # Re-build chunks after purification to ensure consistency
                chunks = self._build_chunks_from_text(rendered_text, original_text=text, preserved_terms=preserved_terms, chunk_size=chunk_size)

            result = {
                "restructured_text": rendered_text,
                "mode": mode,
                "diagnostic_log": diagnostic_log,
                "augmented_words": sorted(list(final_augmented)),
                "chunks": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "highlight_terms": chunk.highlight_terms,
                        "color_terms": chunk.highlight_terms,
                    }
                    for chunk in chunks
                ],
                "metadata": {
                    "font_family": "OpenDyslexic, Atkinson Hyperlegible, sans-serif",
                    "text_size": "1.15rem",
                    "layout": "sentence-per-line",
                    "bilingual_awareness": True,
                    "mode": mode,
                    "preserved_terms": preserved_terms,
                    "ner_protected_terms": ner_protected_terms,
                    "rag_guidance": guidance,
                    "augmentations": self._augmentation_metadata(),
                    "levers": {
                        "aggressiveness": aggressiveness,
                        "playback_speed": f"{playback_speed:.2f}x",
                        "chunk_size": f"{chunk_size} words"
                    }
                },
                "evaluation": {
                    "restructurer": evaluation_metrics,
                },
            }
            return result
        except Exception as e:
            logger.error("CRITICAL RESTRUCTURE ERROR: %s", str(e))
            import traceback
            logger.error(traceback.format_exc())
            # Emergency Fallback: Return original text as chunks
            try:
                chunks = self._build_chunks_from_text(text, original_text=text, preserved_terms=[], chunk_size=20)
                return {
                    "restructured_text": text,
                    "augmented_words": [],
                    "bert_ner_protected": [],
                    "diagnostic_log": {"error": str(e)},
                    "chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "text": chunk.text,
                            "highlight_terms": [],
                        }
                        for chunk in chunks
                    ],
                    "mode": "emergency-fallback",
                }
            except Exception as fallback_error:
                # Absolute last resort
                return {
                    "restructured_text": text,
                    "chunks": [],
                    "error": str(fallback_error)
                }

    def _simplify_text_with_trace(self, text: str, source_context: str, guidance: list[dict], protected_terms: list[str] | None = None, target_language: str = "en", mixed_output: str = "taglish"):
        original_sentence_count = len(self._split_into_sentences(text))
        
        gemma_result, trace = self._try_gemma_simplify_with_trace(
            text=text,
            source_context=source_context,
            guidance=guidance,
            protected_terms=protected_terms,
            target_language=target_language,
            mixed_output=mixed_output,
        )
        
        if gemma_result:
            gemma_text, mode = gemma_result
            
            # 3. Faithfulness Check (Anchor verification) — SKIP FOR LOCAL MODEL
            # Local model is given anchors in the prompt; trust it to preserve them without retry/fallback
            if protected_terms and mode != "local-mt5":
                missing_anchors = [p for p in protected_terms if p.lower() not in gemma_text.lower()]
                if missing_anchors:
                    logger.warning("Anchor Failure detected. Retrying with explicit anchor mandate. Missing: %s", missing_anchors)
                    retry_result, retry_trace = self._try_gemma_simplify_with_trace(
                        text=text,
                        source_context=source_context + f"\nCRITICAL ERROR: YOUR PREVIOUS OUTPUT DELETED THESE PROTECTED WORDS: {', '.join(missing_anchors)}. YOU MUST INCLUDE THEM.",
                        guidance=guidance,
                        protected_terms=protected_terms,
                        target_language=target_language,
                        retry_prompt="MANDATORY ANCHOR INCLUSION RULE",
                        mixed_output=mixed_output,
                    )
                    trace.extend(retry_trace)
                    if retry_result:
                        gemma_text, mode = retry_result
                    
                    # Final verification after retry
                    final_missing = [p for p in protected_terms if p.lower() not in gemma_text.lower()]
                    if final_missing:
                        logger.error("AI persistently failed anchor preservation. Falling back to Lexical Simplifier.")
                        gemma_text = self._lexical_simplify(text, protected_terms)
                        mode = "deterministic-fallback (anchor-protection)"
            
            # 4. LENGTH GOVERNOR: If AI expanded too much (hallucination), retry or truncate.
            input_words = len(text.split())
            output_words = len(gemma_text.split())
            if output_words > (input_words * 1.5) and original_sentence_count == 1:
                logger.warning("Length Governor triggered: AI expanded text too much. Retrying with strict length mandate.")
                retry_result, retry_trace = self._try_gemma_simplify_with_trace(
                    text=text,
                    source_context=source_context + "\nCRITICAL ERROR: YOUR PREVIOUS OUTPUT WAS TOO LONG. DO NOT ADD INFORMATION. USE THE SAME NUMBER OF WORDS AS THE INPUT.",
                    guidance=guidance,
                    protected_terms=protected_terms,
                    target_language=target_language,
                    retry_prompt="STRICT WORD-FOR-WORD SIMPLIFICATION ONLY. NO ADDITIONS.",
                    mixed_output=mixed_output,
                )
                trace.extend(retry_trace)
                if retry_result:
                    gemma_text, mode = retry_result

            if target_language == "tl" and gemma_text:
                # (Tagalog purity checks...)
                text_to_check = gemma_text.lower()
                # Expanded English grammar markers
                english_markers = [
                    " the ", " in ", " and ", " for ", " with ", " is ", " are ", " of ", " this ", " it ", " a ",
                    " to ", " have ", " has ", " been ", " was ", " were ", " by ", " from ", " at ", " as ", " but "
                ]
                if any(marker in text_to_check for marker in english_markers):
                    logger.warning("English leakage detected in Tagalog output. Retrying...")
                    retry_result, retry_trace = self._try_gemma_simplify_with_trace(
                        text=text,
                        source_context=source_context + "\nCRITICAL ERROR: YOUR PREVIOUS OUTPUT HAD ENGLISH GRAMMAR. USE PURE TAGALOG (ang, ng, sa, at, ay). NO ENGLISH ALLOWED.",
                        guidance=guidance,
                        protected_terms=protected_terms,
                        target_language=target_language,
                        retry_prompt="100% PURE TAGALOG MANDATE. NO ENGLISH FILLER WORDS.",
                        mixed_output=mixed_output,
                    )
                    trace.extend(retry_trace)
                    if retry_result:
                        gemma_text, mode = retry_result

            return self._enforce_sentence_structure(gemma_text, original_sentence_count), mode, trace

        return None, "fallback", trace

    def _simplify_text(self, text: str, source_context: str, guidance: list[dict], protected_terms: list[str] | None = None, target_language: str = "en"):
        # Legacy support
        res, mode, trace = self._simplify_text_with_trace(text, source_context, guidance, protected_terms, target_language)
        return res, mode

    def _bulletproof_purify(self, text: str) -> str:
        """Surgically replaces English words and hybrids with pure Tagalog, ignoring syllable dots."""
        return text

    def _lexical_simplify(self, text: str, protected_terms: list[str]) -> str:
        """Lightweight lexical simplifier used as a deterministic fallback when LLM output is unavailable or unchanged."""
        return text

    def _rewrite_passive_to_active_en(self, text: str) -> str:
        """Best-effort passive-to-active rewrites for English without external calls."""
        if not text:
            return ""

        def _rewrite_sentence(sentence: str) -> str:
            sentence = sentence.strip()
            if not sentence:
                return sentence

            end = ""
            if sentence[-1:] in ".!?":
                end = sentence[-1]
                sentence = sentence[:-1].strip()

            # Handles (was/were/is/are) [verb]ed by [agent]
            match = re.search(
                r"\b(?P<object>[a-zA-Z\s]+)\s+(?:was|were|is|are)\s+(?P<verb>[a-z]+ed)\s+by\s+(?P<agent>[a-zA-Z\s]+)(?:\b|$)",
                sentence,
                flags=re.IGNORECASE,
            )
            if not match:
                return f"{sentence}{end}" if end else sentence

            obj = match.group("object").strip()
            verb = match.group("verb").strip()
            agent = match.group("agent").strip()
            if not obj or not agent:
                return f"{sentence}{end}" if end else sentence

            # Handle present/past tense verb conversions
            active_verb = verb
            matched_segment = match.group(0).lower()
            if "is" in matched_segment or "are" in matched_segment:
                if active_verb.endswith("ed"):
                    active_verb = active_verb[:-2]
                if not active_verb.endswith("s"):
                    active_verb += "s"

            # Capitalize agent properly if it's start-of-clause
            is_start_of_sentence = sentence.startswith(match.group(0))
            if is_start_of_sentence:
                agent = agent[:1].upper() + agent[1:]

            rewritten_clause = f"{agent} {active_verb} {obj}"
            rewritten_sentence = sentence.replace(match.group(0), rewritten_clause)
            return f"{rewritten_sentence}{end}" if end else rewritten_sentence

        parts = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        rewritten_parts = [_rewrite_sentence(part) for part in parts]
        return " ".join(rewritten_parts)

    def _is_near_copy(self, original: str, candidate: str) -> bool:
        def normalize(value: str):
            value = str(value or "").lower()
            value = value.replace("Â·", "").replace("·", "")
            value = re.sub(r"^[\s•\-\*]+", "", value, flags=re.MULTILINE)
            value = re.sub(r"[^a-z0-9]+", " ", value)
            return re.sub(r"\s+", " ", value).strip()

        original_norm = normalize(original)
        candidate_norm = normalize(candidate)
        if not original_norm or not candidate_norm:
            return False
        if original_norm == candidate_norm:
            return True

        original_words = original_norm.split()
        candidate_words = candidate_norm.split()
        if len(original_words) >= 5:
            similarity = SequenceMatcher(None, original_words, candidate_words).ratio()
            changed_words = sum(1 for a, b in zip(original_words, candidate_words) if a != b)
            length_delta = abs(len(original_words) - len(candidate_words))
            if similarity >= 0.82 and (changed_words + length_delta) <= 2:
                return True

        if original_words != candidate_words:
            return False

        return len(original_words) >= 4

    def _dynamic_reading_simplify(self, text: str, protected_terms: list[str] | None = None) -> str:
        """Runtime fallback: broadly simplifies hard-looking words and splits dense clauses."""
        return text

    def _rewrite_english_passive_to_active(self, text: str, protected_lower: set[str]) -> str:
        """Convert simple 'X was/were VERBed by Y' sentences into active voice."""
        return text

    def _split_dense_sentence(self, sentence: str) -> list[str]:
        sentence = self._normalize_whitespace(sentence)
        if not sentence:
            return []
        core = sentence.rstrip(".!?").strip()
        parts = [p.strip() for p in re.split(r"\s*(?:;|,)\s*", core) if p.strip()]
        if len(parts) <= 1:
            return [sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."]

        lines = []
        for part in parts:
            part = re.sub(r"^(and|but|or)\s+", "", part, flags=re.IGNORECASE).strip()
            if len(part.split()) <= 2 and lines:
                lines[-1] = lines[-1].rstrip(".!?") + ", " + part + "."
                continue
            if not part:
                continue
            line = part[:1].upper() + part[1:]
            if not line.endswith((".", "!", "?")):
                line += "."
            lines.append(line)
        return lines or [sentence]

    def _try_gemma_simplify_with_trace(self, text: str, source_context: str, guidance: list[dict], protected_terms: list[str] | None = None, retry_prompt: str | None = None, target_language: str = "en", mixed_output: str = "taglish"):
        trace = []
        
        # Route to local model only for English as requested by user
        if target_language in ["en", "english"]:
            trace.append({"step": "groq-simplifier", "duration": 0.0, "status": "skipped (English uses local model only)"})
            return None, trace

        # Tagalog and Mixed use Groq with multilingual Llama 3.3 70B
        import time
        start_time = time.perf_counter()
        
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            trace.append({"step": "groq-simplifier", "duration": round(time.perf_counter() - start_time, 3), "status": "failed (missing API key)"})
            return None, trace

        system_prompt = self._build_simplify_system_prompt(guidance, protected_terms, target_language, source_context, mixed_output)
        
        # Select flagship Llama 3.3 70B model from Groq
        model_name = "llama-3.3-70b-versatile"

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        if target_language in ["tl", "tagalog", "fil", "filipino"]:
            sentence_count = len(self._split_into_sentences(text))
            user_prompt = (
                f"### INPUT TEXT TO SIMALIFY AND RESTRUCTURE:\n"
                f"{text.strip()}\n\n"
                f"### INSTRUCTIONS:\n"
                f"- Restructure and simplify the input text into pure, easy-to-read, and clear Tagalog.\n"
                f"- Do NOT delete any information or facts.\n"
                f"- Do NOT add any extra information, notes, or explanations.\n"
                f"- Retain a 1-to-1 sentence count (input has {sentence_count} sentences).\n"
                f"- Output ONLY the final simplified Tagalog text. No preamble, no postamble."
            )
            if retry_prompt:
                user_prompt += f"\n\n### CRITICAL ADJUSTMENT REQUIRED:\n{retry_prompt}"
        elif target_language in ["mix", "mixed"]:
            sentence_count = len(self._split_into_sentences(text))
            output_lang = str(mixed_output or "taglish").lower().strip()
            user_prompt = (
                f"### INPUT MIXED TEXT TO RESTRUCTURE:\n"
                f"{text.strip()}\n\n"
                f"### INSTRUCTIONS:\n"
                f"- Restructure and simplify the mixed input text into a highly readable, simplified **{output_lang.upper()}** output.\n"
                f"- Do NOT delete any information or facts.\n"
                f"- Do NOT add any extra information, notes, or explanations.\n"
                f"- Retain a 1-to-1 sentence count (input has {sentence_count} sentences).\n"
                f"- Output ONLY the final simplified **{output_lang.upper()}** text. No preamble, no conversational intro."
            )
            if retry_prompt:
                user_prompt += f"\n\n### CRITICAL ADJUSTMENT REQUIRED:\n{retry_prompt}"
        else:
            user_prompt = f"Simplify the following text and rewrite it in the active voice:\n\n{text}"
            if retry_prompt:
                user_prompt += f"\n\nAdditional Instruction: {retry_prompt}"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1024
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                res_data = response.json()
                simplified = res_data["choices"][0]["message"]["content"].strip()
                duration = round(time.perf_counter() - start_time, 3)
                trace.append({"step": "groq-simplifier", "duration": duration, "status": f"success (model: {model_name})"})
                return (simplified, "groq-llama3.3"), trace
            else:
                duration = round(time.perf_counter() - start_time, 3)
                trace.append({"step": "groq-simplifier", "duration": duration, "status": f"failed (HTTP {response.status_code})"})
                logger.error(f"Groq API error (HTTP {response.status_code}): {response.text}")
                return None, trace
        except Exception as e:
            duration = round(time.perf_counter() - start_time, 3)
            trace.append({"step": "groq-simplifier", "duration": duration, "status": f"failed ({str(e)})"})
            logger.error(f"Groq connection exception: {e}")
            return None, trace

    def _try_gemma_simplify_text(self, text: str, source_context: str, guidance: list[dict], protected_terms: list[str] | None = None, retry_prompt: str | None = None, target_language: str = "en"):
        res, trace = self._try_gemma_simplify_with_trace(text, source_context, guidance, protected_terms, retry_prompt, target_language)
        return res

    def _build_simplify_system_prompt(self, guidance: list[dict], protected_terms: list[str] | None = None, target_language: str = "en", source_context: str = "", mixed_output: str = "taglish"):
        protected_text = ", ".join(protected_terms or []) or "none"
        lang_name = "ENGLISH" if target_language == "en" else "TAGALOG"
        
        # Check for Adaptive Aggressiveness
        aggr_mode = "BALANCED"
        if "AGGR:AGGRESSIVE" in source_context:
            aggr_mode = "EXTREME"

        style_mandate = "Use simple words."
        if aggr_mode == "EXTREME":
            style_mandate = "Use the SIMPLEST possible words. Use very short, direct phrases. Prioritize ease of reading over academic style."

        if target_language in ["tl", "tagalog", "fil", "filipino"]:
            return (
                "### ROLE: Expert Tagalog Text Simplifier and Restructuring Specialist\n"
                "### MANDATE: Complete faithfulness to the original meaning. Simplify and restructure the text into clear, easy-to-read, understandable Tagalog without adding or deleting any facts or information.\n"
                f"### AGGRESSIVENESS: {aggr_mode}\n"
                "### ABSOLUTE RULES:\n"
                "1. DO NOT DELETE INFORMATION: Retain all original facts, events, relations, and core meaning. Do not skip or omit any details.\n"
                "2. DO NOT ADD INFORMATION: Do not introduce any new information, external facts, examples, explanations, or interpretations. Keep only what was in the input text.\n"
                "3. SIMPLIFY & RESTRUCTURE: Translate difficult, complex, or formal words into simple, common, and highly readable Tagalog. Restructure long, dense, or passive-voice sentences into clear, direct, active-voice Tagalog sentences.\n"
                "4. PURE TAGALOG: Write in natural, pure Tagalog using standard grammar. Avoid mixing English/Taglish unless a term is a proper noun or technical word that cannot be translated.\n"
                "5. 1-to-1 SENTENCE RATIO: You must produce the exact same number of sentences as the input text. Each input sentence should correspond to exactly one simplified/restructured sentence in the output.\n"
                "6. MANDATORY ANCHORS: You MUST include these exact terms in your simplified sentences: " + protected_text + "\n"
                "7. NO PREAMBLE OR EXPLANATIONS: Do not output any notes, introductory phrases (like 'Narito ang...'), or conversational text. Start immediately with the simplified sentence, and return ONLY the simplified Tagalog text.\n"
            )

        if target_language in ["mix", "mixed"]:
            output_lang = str(mixed_output or "taglish").lower().strip()
            if output_lang == "tagalog":
                return (
                    "### ROLE: Expert Tagalog Translator and Text Simplifier\n"
                    "### MANDATE: Translate all English portions of the mixed input text and simplify the entire text into clear, easy-to-read, PURE Tagalog without adding or deleting any facts.\n"
                    f"### AGGRESSIVENESS: {aggr_mode}\n"
                    "### ABSOLUTE RULES:\n"
                    "1. PURE TAGALOG ONLY: The entire output must be in pure Tagalog. Translate all English phrases and words to standard Tagalog equivalents.\n"
                    "2. DO NOT DELETE INFORMATION: Retain all original facts, events, and meaning.\n"
                    "3. DO NOT ADD INFORMATION: No explanations, no preamble, and no conversational introductory words.\n"
                    "4. 1-to-1 SENTENCE RATIO: Keep the exact same sentence count as the input.\n"
                    "5. MANDATORY ANCHORS: You MUST include these exact terms: " + protected_text + "\n"
                )
            elif output_lang == "english":
                return (
                    "### ROLE: Expert English Translator and Text Simplifier\n"
                    "### MANDATE: Translate all Tagalog portions of the mixed input text and simplify the entire text into clear, easy-to-read, PURE English without adding or deleting any facts.\n"
                    f"### AGGRESSIVENESS: {aggr_mode}\n"
                    "### ABSOLUTE RULES:\n"
                    "1. PURE ENGLISH ONLY: The entire output must be in pure English. Translate all Tagalog phrases and words to clear English equivalents.\n"
                    "2. DO NOT DELETE INFORMATION: Retain all original facts, events, and meaning.\n"
                    "3. DO NOT ADD INFORMATION: No explanations, no preamble.\n"
                    "4. 1-to-1 SENTENCE RATIO: Keep the exact same sentence count as the input.\n"
                    "5. MANDATORY ANCHORS: You MUST include these exact terms: " + protected_text + "\n"
                )
            else:
                return (
                    "### ROLE: Expert Taglish Text Simplifier and Restructurer\n"
                    "### MANDATE: Simplify and restructure the mixed English/Tagalog input text into highly readable and conversational Taglish (a natural blend of Tagalog and English for maximum clarity for local readers).\n"
                    f"### AGGRESSIVENESS: {aggr_mode}\n"
                    "### ABSOLUTE RULES:\n"
                    "1. NATURAL TAGLISH BLEND: Blend Tagalog and English naturally as local speakers do, prioritizing maximum readability and ease of understanding.\n"
                    "2. DO NOT DELETE INFORMATION: Keep all original facts and details.\n"
                    "3. DO NOT ADD INFORMATION: No intro/outro notes, explanations, or preambles.\n"
                    "4. 1-to-1 SENTENCE RATIO: Keep the exact same sentence count as the input.\n"
                    "5. MANDATORY ANCHORS: You MUST include these terms: " + protected_text + "\n"
                )

        return (
            f"### ROLE: Surgical {lang_name} Word-Replacer\n"
            f"### MANDATE: 1-to-1 FAITHFULNESS. RETURN ONLY THE RESTRUCTURED TEXT IN PURE {lang_name}.\n"
            f"### AGGRESSIVENESS: {aggr_mode}\n"
            "### ABSOLUTE RULES:\n"
            f"1. PURE {lang_name} ONLY: You must translate and simplify everything into pure {lang_name}.\n"
            f"2. NO EXPANSION: Do not add any information. {style_mandate}\n"
            "3. NO DELETION: Do not remove any information from the input.\n"
            "4. 1-to-1 SENTENCE RATIO: Use the exact same number of sentences as the input.\n"
            "5. NO PREAMBLE: Start with the first word. No 'Here is...' or 'Simplified text:'.\n"
            "6. MANDATORY ANCHORS: You MUST include these words: " + protected_text + "\n"
        )

    def _translate_anchor_list(self, terms: list[str], target_name: str):
        """Surgically translates keywords into the target language."""
        return terms

    def _split_into_sentences(self, text: str) -> list[str]:
        if not text:
            return []
        
        # 1. CLEANING: Remove internal newlines that cause fragmentation
        text = text.replace('\n', ' ').strip()
        text = re.sub(r'\s+', ' ', text)
        
        # 2. SURGICAL SPLIT: Only split on . ! ? followed by a space or end of string
        # This prevents splitting on abbreviations or middle of phrases
        raw_sentences = re.split(r"([.!?](?:\s|$))", text)
        
        sentences = []
        current = ""
        for part in raw_sentences:
            if re.match(r"[.!?](?:\s|$)", part):
                current += part.strip()
                sentences.append(current.strip())
                current = ""
            else:
                current += part
        
        if current.strip():
            sentences.append(current.strip())
            
        # 3. FRAGMENT GLUING: If a "sentence" is too short (like "ng"), glue it to the previous one
        glued_sentences = []
        for s in sentences:
            if not glued_sentences:
                glued_sentences.append(s)
            else:
                # If the current sentence is just a fragment (less than 5 chars or 1 word), glue it
                if len(s.split()) <= 1 or len(s) < 5:
                    glued_sentences[-1] = glued_sentences[-1] + " " + s
                else:
                    glued_sentences.append(s)
        
        return [s.strip() for s in glued_sentences if s.strip()]

    def generate_groq_audio(self, text: str, lang: str):
        """
        Generates high-quality neural audio with a TRIPLE-engine fallback strategy.
        Optimized for < 200 characters to ensure stability.
        """
        import requests
        import urllib.parse
        
        # Google Neural engine works best with < 200 characters
        encoded_text = urllib.parse.quote(text[:200])
        tts_lang = 'tl' if lang == 'tl' else 'en'
        
        # THREE ENGINES FOR 100% RELIABILITY
        urls = [
            f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={tts_lang}&client=tw-ob",
            f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={tts_lang}&client=gtx",
            f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={tts_lang}&client=t"
        ]
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Referer": "https://translate.google.com/"
        }

        for url in urls:
            try:
                # Increased timeout to 10s to allow for neural generation
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return response.content
            except Exception as e:
                print(f"Neural Engine attempt failed: {e}")
                continue
                
        return None

    def get_neural_tts_url(self, text: str, lang: str):
        """
        Generates a high-quality neural TTS URL. 
        Prioritizes the fastest free engines that support Tagalog word-flows.
        """
        import urllib.parse
        encoded_text = urllib.parse.quote(text[:200]) # Cap for stability
        
        if lang == 'tl':
            # Google Translate TTS is the best FREE word-based Tagalog engine (doesn't spell letters)
            return f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=tl&client=tw-ob"
        else:
            # High-quality English fallback
            return f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl=en&client=tw-ob"

    def _build_simplify_user_prompt(self, text: str, source_context: str, protected_terms: list[str] | None = None, target_language: str = "en"):
        protected_text = ", ".join(protected_terms or []) or "none"
        lang_name = "ENGLISH" if target_language == "en" else "TAGALOG"
        return (
            f"INPUT_TEXT: {text.strip()}\n"
            f"MANDATORY_ANCHORS: {protected_text}\n"
            f"TARGET_LANGUAGE: PURE {lang_name}\n"
            f"TASK: Restructure the input text into simple {lang_name} for a dyslexic student. DO NOT add info. DO NOT delete info. Return ONLY the simplified {lang_name} paragraph."
        )

    def _enforce_sentence_structure(self, text: str, target_count: int):
        # 0. NUCLEAR SILENCE: Remove common AI 'Notes' or 'Reminders'
        text = re.split(r"(?i)\n*(?:Note|NOTE|Reminder|REMINDER|Swapped words|Here is the|Simplified|Anchors|Explanation|Summary):", text)[0].strip()
        text = re.sub(r"\(Note:.*?\)", "", text, flags=re.IGNORECASE).strip()
        
        normalized = self._normalize_whitespace(text)
        # Robust sentence splitting: split on any [.!?] followed by space or end of string
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s*", normalized) if s.strip()]
        
        # 1. CLEANING & NORMALIZATION
        finalized = []
        seen_sentences = set()
        for sentence in sentences:
            clean_sentence = self._normalize_whitespace(sentence)
            if not clean_sentence or clean_sentence.lower() in seen_sentences:
                continue
            seen_sentences.add(clean_sentence.lower())
            finalized.append(clean_sentence)

        # 2. Keep information even if the model split a dense sentence.
        if len(finalized) > target_count:
            logger.warning("Sentence merge: AI split dense text (%d vs %d). Merging overflow instead of deleting it.", len(finalized), target_count)
            if target_count <= 1:
                finalized = [" ".join(finalized)]
            else:
                finalized = finalized[: target_count - 1] + [" ".join(finalized[target_count - 1:])]

        return " ".join(finalized) if finalized else normalized

    def _split_into_sentences(self, text: str) -> list[str]:
        if not text:
            return []
        if self.nlp:
            doc = self.nlp(text)
            return [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        # Fallback if spacy failed to load
        return [s.strip() for s in SENTENCE_SPLIT_PATTERN.split(text) if s.strip()]

    def _split_long_sentences(self, sentence: str) -> list[str]:
        if not self.nlp:
            # Basic fallback if spacy not available
            words = sentence.split()
            if len(words) <= 22:
                s = self._process_single_sentence(sentence)
                return [s] if s else []
            return [self._process_single_sentence(sentence)]

        doc = self.nlp(sentence)
        words = [t for t in doc if not t.is_punct]
        
        # Only split if it's actually long
        if len(words) <= 15:
            s = self._process_single_sentence(sentence)
            return [s] if s else []

        # Find the best split point using SpaCy dependency parsing
        # We look for a coordinating conjunction (CC) or a subord (SCONJ)
        best_split_idx = -1
        
        # Priority 1: Semicolons
        for token in doc:
            if token.text == ";":
                best_split_idx = token.i
                break
        
        # Priority 2: Conjunctions with their own subjects
        if best_split_idx == -1:
            for token in doc:
                if token.pos_ in ["CCONJ", "SCONJ"] and token.i > 5 and token.i < len(doc) - 5:
                    # Check if there's a verb after the conjunction (to avoid fragments)
                    has_verb_after = any(t.pos_ == "VERB" for t in doc[token.i:])
                    if has_verb_after:
                        best_split_idx = token.i
                        break
        
        if best_split_idx != -1:
            p1 = doc[:best_split_idx].text.strip()
            p2 = doc[best_split_idx:].text.strip()
            # If the split starts with a connector, keep it but capitalize
            p2 = p2[0].upper() + p2[1:]
            return self._split_long_sentences(p1) + self._split_long_sentences(p2)

        # If no smart split found, process as one
        s = self._process_single_sentence(sentence)
        return [s] if s else []

    def _has_verb(self, text: str) -> bool:
        if self.nlp:
            doc = self.nlp(text)
            return any(t.pos_ == "VERB" for t in doc)
        # Old heuristic fallback
        return any(v in text.lower() for v in COMMON_ACADEMIC_VERBS)

    def _process_single_sentence(self, sentence: str):
        s = self._ensure_subject_first(sentence)
        s = self._ensure_who_did_what(s)
        s = self._normalize_sentence_start(s)
        if s and not s.endswith((".", "!", "?")):
            s += "."
        return s

    def _ensure_subject_first(self, sentence: str):
        text = self._normalize_whitespace(sentence)
        if not text:
            return text

        first_word_match = re.match(r"^([A-Za-z][A-Za-z\-']*)([\s,]+)?", text)
        if not first_word_match:
            return text

        first_word = first_word_match.group(1)
        first_word_lower = first_word.lower()

        if first_word_lower in {marker.lower() for marker in LEADING_DISCOURSE_MARKERS}:
            remainder = text[first_word_match.end():].lstrip(" ,")
            if remainder:
                text = remainder
            else:
                return text

        first_token = re.match(r"^([A-Za-z][A-Za-z\-']*)", text)
        if not first_token:
            return text

        first_token_text = first_token.group(1)
        first_token_lower = first_token_text.lower()
        noun_like_start = (
            first_token_text[:1].isupper()
            or first_token_lower in {"the", "a", "an"}
            or bool(re.fullmatch(r"[A-Z]{2,}[A-Z0-9\-]*", first_token_text))
        )

        if noun_like_start:
            return text

        if first_token_lower in {
            "it",
            "this",
            "that",
            "these",
            "those",
            "there",
            "they",
            "we",
            "you",
            "i",
            "he",
            "she",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
        } or first_token_lower.endswith(("ed", "ing")):
            return f"The {text[0].lower() + text[1:]}"

        return text

    def _ensure_who_did_what(self, sentence: str):
        # We now trust the AI to provide complete sentences.
        # Manual 'repair' logic was injecting unwanted filler phrases like 'is important'.
        return self._normalize_whitespace(sentence)

    def _should_apply_syllable_chunking(self, source_context: str):
        # Disabled at user request to avoid cutting words
        return False

    def _build_chunks_from_text(self, text: str, original_text: str, preserved_terms: list[str] | None = None, chunk_size: int = 20):
        """Builds chunks where each sentence is its own chunk, ignoring word counts."""
        # Use a robust split that ignores syllable markers but catches sentence ends
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        
        if preserved_terms is None:
            preserved_terms = self._extract_preserved_terms(original_text)
        chunks = []

        for idx, normalized_sentence in enumerate(sentences, 1):
            highlight_terms = self._terms_present_in_text(normalized_sentence, preserved_terms)
            chunks.append(
                RestructuredChunk(
                    chunk_id=f"chunk-{idx}",
                    text=normalized_sentence,
                    highlight_terms=highlight_terms,
                )
            )

        return chunks or [
            RestructuredChunk(chunk_id="chunk-1", text=text.strip(), highlight_terms=[])
        ]

    def _terms_present_in_text(self, text: str, terms: list[str]):
        present = []
        for term in terms:
            pattern = re.compile(rf"\b{re.escape(term)}\b", flags=re.IGNORECASE)
            if pattern.search(text):
                present.append(term)
        return present

    def _extract_response_text(self, response):
        content = getattr(response, "content", None) or []
        text_parts = []
        for block in content:
            block_text = getattr(block, "text", None)
            if block_text:
                text_parts.append(block_text)
        return "\n".join(text_parts).strip()

    def _safe_parse_json(self, text: str):
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)

        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _normalize_llm_response(self, payload: dict, original_text: str, guidance: list[dict]):
        chunks = payload.get("chunks") or []
        normalized_chunks = []

        for index, chunk in enumerate(chunks, start=1):
            text = self._strip_syllable_markers(self._coerce_text(chunk.get("text")))
            highlight_terms = self._coerce_string_list(chunk.get("highlight_terms"))
            color_terms = self._coerce_string_list(chunk.get("color_terms"))
            normalized_chunks.append(
                {
                    "chunk_id": str(chunk.get("chunk_id") or f"chunk-{index}"),
                    "text": text,
                    "highlight_terms": highlight_terms,
                    "color_terms": color_terms or highlight_terms,
                }
            )

        if not normalized_chunks:
            normalized_chunks = [
                {
                    "chunk_id": "chunk-1",
                    "text": original_text.strip(),
                    "highlight_terms": self._extract_preserved_terms(original_text),
                    "color_terms": self._extract_preserved_terms(original_text),
                }
            ]

        restructured_text = payload.get("restructured_text")
        if not restructured_text:
            restructured_text = "\n".join(chunk["text"] for chunk in normalized_chunks if chunk["text"])
        restructured_text = self._strip_syllable_markers(restructured_text)

        metadata = payload.get("metadata") or {}
        metadata.update(
            {
                "font_family": metadata.get("font_family") or "OpenDyslexic, Atkinson Hyperlegible, sans-serif",
                "text_size": metadata.get("text_size") or "1.15rem",
                "layout": metadata.get("layout") or "sentence-per-line",
                "bilingual_awareness": True,
                "rag_guidance": guidance,
                "preserved_terms": metadata.get("preserved_terms") or self._extract_preserved_terms(original_text),
                "mode": "anthropic",
                "augmentations": metadata.get("augmentations") or self._augmentation_metadata(),
            }
        )

        return {
            "restructured_text": restructured_text,
            "chunks": normalized_chunks,
            "metadata": metadata,
        }

    def _coerce_text(self, value):
        return str(value or "").strip()

    def _coerce_string_list(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if not isinstance(value, (list, tuple, set)):
            return []

        normalized = []
        for item in value:
            text = str(item or "").strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    def _augmentation_metadata(self):
        return {
            "syllable_chunk_spacer": {
                "enabled": True,
                "marker": "·",
                "description": "Insert middle dots between syllable chunks in words with 3+ syllables.",
            },
            "font_change": {
                "enabled": True,
                "font_family": "OpenDyslexic, Atkinson Hyperlegible, sans-serif",
            },
            "text_size_change": {
                "enabled": True,
                "text_size": "1.15rem",
            },
            "text_color_change": {
                "enabled": True,
                "source": "highlight_terms and color_terms",
            },
            "text_divider": {
                "enabled": True,
                "mode": "sentence-per-line",
            },
            "text_simplifier": {
                "enabled": True,
                "mode": "base-term-replacement-and-active-voice",
            },
        }

    def _build_guidance(self, text: str, source_context: str):
        query = f"{source_context} {text}".strip()
        documents = self.corpus.retrieve(query)
        if not documents:
            return []
        return [
            {
                "title": document.title,
                "content": document.content[:500],
            }
            for document in documents
        ]

    def _build_chunks(self, text: str):
        sentences = self._split_into_sentences(text)
        chunks = []

        for index, sentence in enumerate(sentences, start=1):
            simplified_sentence = self._simplify_sentence(sentence)
            highlight_terms = self._extract_preserved_terms(sentence)
            chunks.append(
                RestructuredChunk(
                    chunk_id=f"chunk-{index}",
                    text=simplified_sentence,
                    highlight_terms=highlight_terms,
                )
            )

        return chunks

    def _simplify_sentence(self, sentence: str):
        sentence = sentence.strip()
        sentence = self._convert_passive_to_active(sentence)
        sentence = self._normalize_sentence_start(sentence)
        sentence = re.sub(r"\s+", " ", sentence)
        if not sentence.endswith((".", "!", "?")):
            sentence += "."
        return sentence

    def _apply_syllable_chunking_to_text(self, text: str):
        tokens = re.split(r"(\W+)", text)
        rewritten_tokens = []

        for token in tokens:
            if not token or re.fullmatch(r"\W+", token):
                rewritten_tokens.append(token)
                continue

            # Chunk all words that have 3+ syllables
            rewritten_tokens.append(self._syllable_chunk(token))

        return "".join(rewritten_tokens)

    def _apply_syllable_chunking_to_all_long_words(self, text: str):
        """Apply syllable chunking to EVERY word with 3+ syllables."""
        if not text:
            return text
        
        tokens = re.split(r"(\W+)", text)
        rewritten_tokens = []

        for token in tokens:
            if not token or re.fullmatch(r"\W+", token):
                rewritten_tokens.append(token)
                continue

            # Check syllable count and chunk if 3+
            if self._estimate_syllable_count(token) >= 3:
                rewritten_tokens.append(self._syllable_chunk(token))
            else:
                rewritten_tokens.append(token)

        return "".join(rewritten_tokens)

    def _apply_syllable_chunking_to_augmented(self, text: str, augmented_words: list[str]):
        """Apply syllable chunking only to augmented (complex) words."""
        if not augmented_words:
            return text
        
        augmented_lower = {w.lower(): w for w in augmented_words}
        tokens = re.split(r"(\W+)", text)
        rewritten_tokens = []

        for token in tokens:
            if not token or re.fullmatch(r"\W+", token):
                rewritten_tokens.append(token)
                continue

            # Only chunk if this token matches an augmented word
            if token.lower() in augmented_lower:
                rewritten_tokens.append(self._syllable_chunk(token))
            else:
                rewritten_tokens.append(token)

        return "".join(rewritten_tokens)

    def _normalize_whitespace(self, text: str):
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        return re.sub(r"\s+([,.!?;:])", r"\1", compact)

    def _strip_syllable_markers(self, text: str):
        # Remove explicit syllable separators while preserving hyphenated technical terms.
        cleaned = str(text or "")
        cleaned = cleaned.replace("·", "")
        return re.sub(r"\s+", " ", cleaned).strip()

    def _extract_original_complex_words(self, text: str):
        # We don't extract from input anymore. 
        # We let the AI simplify first, then we syllable-chunk the result!
        return []

    def _normalize_sentence_start(self, sentence: str):
        if not sentence:
            return sentence
        
        # Enforce Completeness Rule: Never start with a Verb
        if self.nlp:
            doc = self.nlp(sentence)
            if len(doc) > 0 and doc[0].pos_ == "VERB":
                # Enforce "Subject + Verb" by prepending "This " to verb-only starts
                return "This " + sentence[:1].lower() + sentence[1:]

        return sentence[:1].upper() + sentence[1:]

    def _convert_passive_to_active(self, sentence: str):
        extraposition_match = re.match(
            r"^It\s+(?P<aux>has|have|had|is|are|was|were)\s+been\s+(?P<verb>[A-Za-z]+ed|known|made|given|seen|taken|used|shown|found|built|based)\s+by\s+(?P<agent>.+?)\s+that\s+(?P<clause>.+?)(?P<tail>[.!?])?$",
            sentence,
            flags=re.IGNORECASE,
        )
        if extraposition_match:
            agent = extraposition_match.group("agent").strip()
            verb = extraposition_match.group("verb").strip()
            clause = extraposition_match.group("clause").strip()
            return f"{agent} {verb} that {clause}"

        passive_match = re.match(
            r"^(?P<object>.+?)\s+(?P<be>was|were|is|are|been|be|being)\s+(?P<verb>[A-Za-z]+ed|known|made|given|seen|taken|used|shown|found|built|based)\s+by\s+(?P<agent>.+?)(?P<tail>[.!?])?$",
            sentence,
            flags=re.IGNORECASE,
        )
        if not passive_match:
            return sentence

        agent = passive_match.group("agent").strip()
        verb = passive_match.group("verb").strip()
        obj = self._normalize_moved_object_phrase(passive_match.group("object").strip())
        return f"{agent} {verb} {obj}"

    def _normalize_moved_object_phrase(self, phrase: str):
        # If an object phrase starts with an article and now appears mid-sentence,
        # normalize it to lowercase unless it likely begins a proper name.
        match = re.match(r"^(The|A|An)(\s+)([A-Za-z])", phrase)
        if not match:
            return phrase

        if match.group(3).islower():
            article = match.group(1).lower()
            return article + phrase[len(match.group(1)) :]

        return phrase

    def _chunk_complex_words(self, sentence: str):
        preserved_terms = set(self._extract_preserved_terms(sentence))
        tokens = re.split(r"(\W+)", sentence)
        rewritten_tokens = []

        for token in tokens:
            if not token or re.fullmatch(r"\W+", token):
                rewritten_tokens.append(token)
                continue

            if token in preserved_terms or self._should_preserve_token(token):
                rewritten_tokens.append(token)
                continue

            rewritten_tokens.append(self._syllable_chunk(token))

        return "".join(rewritten_tokens)

    def _should_preserve_token(self, token: str):
        return bool(re.fullmatch(r"[A-Z]{2,}[A-Z0-9\-]*", token)) or bool(re.fullmatch(r"[A-Z][a-z]+", token))

    def _syllable_chunk(self, word: str):
        if not re.search(r"[A-Za-z]", word):
            return word

        if self._estimate_syllable_count(word) < 3:
            return word

        if "-" in word:
            return "-".join(self._syllable_chunk(part) for part in word.split("-"))

        pieces = []
        lower = word.lower()
        index = 0
        while index < len(lower):
            match = re.match(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy](?![aeiouy]))?", lower[index:])
            if not match:
                pieces.append(lower[index:])
                break
            chunk = match.group(0)
            pieces.append(chunk)
            index += len(chunk)

        chunked = "·".join(piece for piece in pieces if piece)
        return self._match_case(word, chunked)

    def _estimate_syllable_count(self, word: str):
        cleaned_word = re.sub(r"[^A-Za-z]", "", word).lower()
        if not cleaned_word:
            return 0

        groups = re.findall(r"[aeiouy]+", cleaned_word)
        count = len(groups)

        if cleaned_word.endswith("e") and count > 1:
            count -= 1

        return max(count, 1)

    def _match_case(self, original: str, transformed: str):
        if original.isupper():
            return transformed.upper()
        if original[:1].isupper():
            return transformed[:1].upper() + transformed[1:]
        return transformed

    def _extract_preserved_terms(self, text: str):
        terms = set()
        # 1. ONLY protect Acronyms (WHO, NASA, DNA)
        terms.update(re.findall(r"\b[A-Z]{2,}[A-Z0-9\-]*\b", text))
        
        # 2. ONLY protect Proper Name patterns (Upper Case names)
        # We exclude common start-of-sentence words later
        terms.update(match.group(0) for match in re.finditer(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text))
        
        # (Removed all length-based and suffix-based protection)

        filtered_terms = [
            term for term in terms if term.strip().lower() not in NON_PRESERVED_CAPITALIZED_WORDS
        ]
        # Remove very common words that might have been caught by mistake
        common_words = {"their", "there", "these", "those", "about", "would", "could", "should", "people", "really"}
        filtered_terms = [t for t in filtered_terms if t.lower() not in common_words]
        
        return sorted(filtered_terms, key=len, reverse=True)


    def _should_apply_syllable_chunking(self, source_context: str):
        # Disabled at user request to avoid cutting words
        return False

def get_restructurer_service():
    return ReadingRestructurerService()
