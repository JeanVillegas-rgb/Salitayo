"""
Spelling analysis pipeline.

For each word in the input text that appears misspelled:
  1. SymSpell candidate generation
  2. T5-small reranker
  3. RandomForest error classifier

Contextual alignment (RAG + NLI) runs separately via alignment_pipeline.py
and is triggered only on explicit user request.
"""
import logging
import re
import time

import editdistance

from .candidate_generator import get_candidates, is_known_word
from .error_classifier_service import classify_error
from .reranker_service import rerank

logger = logging.getLogger(__name__)

_ERROR_FEEDBACK = {
    "phonetic_sub": "You substituted a letter with one that sounds similar.",
    "reversal": "You reversed one or more letters.",
    "omission": "You omitted a letter.",
    "insertion": "You added an extra letter.",
    "transposition": "You swapped two adjacent letters.",
}


def _apply_reranker_fallbacks(word: str, reranked: str, candidates: list[str]) -> str:
    """
    Four post-reranker sanity checks applied in order.

    Check 0a — edit-distance rank: the reranker must never pick a word that is
    further from the misspelled input than candidates[0]. SymSpell already ranks
    by (edit_distance ASC, frequency DESC), so candidates[0] is the closest
    match. Overriding it with something further is always wrong.

    Check 0b — character coverage tie-break: when the reranker's pick and
    candidates[0] have equal edit distance, prefer the one that shares more
    characters with the misspelled word. Handles cases like scohol→spool vs
    school where both have ed=2 but 'c' and 'h' from scohol are absent in spool.

    Check 1 — length: if the reranked pick is 2+ characters shorter than the
    misspelled word, fall back to the first candidate that is at least as long.

    Check 2 — edit distance ceiling: if edit_distance > len(word)/2, the pick
    is implausible; fall back to candidates[0].
    """
    word_lower = word.lower()
    ed_reranked = editdistance.eval(word_lower, reranked)
    ed_top = editdistance.eval(word_lower, candidates[0])

    # Check 0a: reranker chose something further from the input than candidates[0].
    if ed_reranked > ed_top:
        logger.debug(
            f"[FALLBACK]   0a ed-rank: dist('{word}','{reranked}')={ed_reranked} > "
            f"dist('{word}','{candidates[0]}')={ed_top} → prefer '{candidates[0]}'"
        )
        return candidates[0]

    # Check 0b: equal edit distance but reranker's pick shares fewer input chars.
    if ed_reranked == ed_top and reranked != candidates[0]:
        reranked_set = set(reranked)
        top_set = set(candidates[0])
        miss_reranked = sum(1 for c in word_lower if c not in reranked_set)
        miss_top = sum(1 for c in word_lower if c not in top_set)
        if miss_reranked > miss_top:
            logger.debug(
                f"[FALLBACK]   0b char-coverage: '{reranked}' missing {miss_reranked} "
                f"chars of '{word}', '{candidates[0]}' missing {miss_top} → "
                f"prefer '{candidates[0]}'"
            )
            return candidates[0]

    # Check 1: reranked word is 2+ characters shorter than the misspelled word.
    if len(reranked) < len(word_lower) - 1:
        longer = next(
            (c for c in candidates if len(c) >= len(word_lower)), None
        )
        if longer:
            logger.debug(
                f"[FALLBACK]   1 length: '{reranked}' ({len(reranked)}) is >=2 chars "
                f"shorter than '{word}' ({len(word_lower)}) → switching to '{longer}'"
            )
            return longer

    # Check 2: edit distance exceeds half the misspelled word's length.
    if ed_reranked > len(word_lower) / 2:
        logger.debug(
            f"[FALLBACK]   2 ed-ceil: dist('{word}','{reranked}')={ed_reranked} "
            f"> {len(word_lower)/2:.1f} → falling back to '{candidates[0]}'"
        )
        return candidates[0]

    return reranked


def _tokenize(text: str) -> list[tuple[str, int, int]]:
    """Return list of (word, start, end) for alphabetic tokens."""
    return [(m.group(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z]+", text)]


def analyze(text: str) -> dict:
    start_ms = time.time()

    logger.debug("=" * 60)
    logger.debug(f"[PIPELINE] Input text : {repr(text)}")

    tokens = _tokenize(text)
    logger.debug(f"[PIPELINE] Tokens ({len(tokens)}): {[w for w, _, _ in tokens]}")

    errors = []
    corrected_text = text
    offset = 0

    for word, start, end in tokens:
        if is_known_word(word):
            logger.debug(f"[PIPELINE]   '{word}' → known, skip")
            continue

        candidates = get_candidates(word, max_candidates=5)
        logger.debug(f"[CANDIDATES] '{word}' → {candidates}")

        if not candidates or candidates[0] == word.lower():
            logger.debug(f"[PIPELINE]   '{word}' → no improvement, skip")
            continue

        best = rerank(word, candidates)
        best = _apply_reranker_fallbacks(word, best, candidates)
        logger.debug(f"[RERANKER]   '{word}' → final='{best}'")

        error_info = classify_error(word, best)
        logger.debug(
            f"[CLASSIFIER] '{word}'→'{best}' "
            f"type={error_info['error_type']} "
            f"conf={error_info['confidence'] * 100:.1f}%  "
            f"all={error_info['probabilities']}"
        )

        adj_start = start + offset
        adj_end = end + offset
        corrected_text = corrected_text[:adj_start] + best + corrected_text[adj_end:]

        errors.append({
            "word": word,
            "start": start,
            "end": end,
            "error_type": error_info["error_type"],
            "error_type_label": error_info["label"],
            "error_type_confidence": error_info["confidence"],
            "correction": best,
            "candidates": candidates,
            "feedback": _ERROR_FEEDBACK.get(
                error_info["error_type"], "Spelling error detected."
            ),
        })

        offset += len(best) - len(word)

    elapsed_ms = round((time.time() - start_ms) * 1000)
    logger.debug(f"[PIPELINE] Done: {len(errors)} error(s) | {elapsed_ms}ms")
    logger.debug("=" * 60)

    return {
        "original_text": text,
        "corrected_text": corrected_text,
        "word_count": len(tokens),
        "error_count": len(errors),
        "errors": errors,
        "processing_time_ms": elapsed_ms,
    }
