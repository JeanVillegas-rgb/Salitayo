"""
Sentence-level contextual alignment pipeline.

Called only on explicit user request — never during spelling analysis.

Input: the learner's current text (with accepted corrections applied)
       + the full reference passage.

For each learner sentence:
  1. spaCy sentence segmentation on both texts
  2. RAG retrieval — paraphrase-MiniLM-L3-v2 finds the closest reference sentence
  3. DeBERTa NLI — hypothesis is the (already-corrected) learner sentence
"""
import logging
import time

import spacy

from .nli_aligner_service import align
from .retrieval_service import retrieve_best_sentence

logger = logging.getLogger(__name__)

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def _split_sentences(text: str) -> list[str]:
    doc = _get_nlp()(text)
    return [s.text.strip() for s in doc.sents if s.text.strip()]


def run_alignment(text: str, reference_passage: str) -> list[dict]:
    """
    text is the learner's current text with accepted spelling corrections applied.
    Returns a list of context_alignment_results dicts.
    """
    start_ms = time.time()

    logger.debug("=" * 60)
    logger.debug(f"[ALIGNMENT] Input text : {repr(text)}")
    logger.debug(f"[ALIGNMENT] Reference  : {len(reference_passage.split())} words")

    ref_sentences = _split_sentences(reference_passage)
    learner_sentences = _split_sentences(text)

    logger.debug(
        f"[ALIGNMENT] Reference sentences ({len(ref_sentences)}): "
        f"{[s[:50] for s in ref_sentences[:5]]}"
    )
    logger.debug(
        f"[ALIGNMENT] Learner sentences ({len(learner_sentences)}): "
        f"{[s[:50] for s in learner_sentences]}"
    )

    results = []

    if not ref_sentences:
        logger.debug("[ALIGNMENT] No reference sentences — skipping.")
        return results

    for learner_sent in learner_sentences:
        best_ref, sim_score = retrieve_best_sentence(learner_sent, ref_sentences)

        nli_result = align(best_ref, learner_sent)
        logger.debug(
            f"[ALIGNMENT] learner: {repr(learner_sent[:60])} | "
            f"ref: {repr(best_ref[:60])} | "
            f"label={nli_result['label']} "
            f"conf={nli_result['confidence'] * 100:.1f}%"
        )

        results.append({
            "learner_sentence": learner_sent,
            "reference_sentence": best_ref,
            "similarity_score": round(sim_score, 4),
            "nli_label": nli_result["label"],
            "nli_confidence": nli_result["confidence"],
        })

    elapsed_ms = round((time.time() - start_ms) * 1000)
    logger.debug(f"[ALIGNMENT] Done: {len(results)} result(s) | {elapsed_ms}ms")
    logger.debug("=" * 60)

    return results
