"""
T5-small spelling reranker. Given a misspelled word and SymSpell candidates,
generates the best correction via seq2seq decoding.

Input format: "correct: {misspelled} options: {c1} | {c2} | {c3} | {c4} | {c5}"
Output: best correction token(s).

NOTE: Verify this input format matches your T5 training script's preprocessing.
"""
import logging
import os
import torch
from django.conf import settings
from transformers import T5ForConditionalGeneration, T5Tokenizer

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None


def _load():
    global _model, _tokenizer
    if _model is None:
        model_dir = os.path.join(settings.TRAINED_MODELS_DIR, "reranker", "final_model")
        _tokenizer = T5Tokenizer.from_pretrained(model_dir)
        _model = T5ForConditionalGeneration.from_pretrained(model_dir)
        _model.eval()
    return _model, _tokenizer


def rerank(misspelled: str, candidates: list[str]) -> str:
    """
    Returns the top-ranked correction for `misspelled` given `candidates`.
    Falls back to the first candidate if generation fails.
    """
    if not candidates:
        return misspelled

    model, tokenizer = _load()
    candidate_str = " | ".join(candidates)
    input_text = f"correct: {misspelled} options: {candidate_str}"

    inputs = tokenizer(
        input_text,
        return_tensors="pt",
        max_length=128,
        truncation=True,
    )

    with torch.no_grad():
        output_ids = model.generate(
            inputs["input_ids"],
            max_new_tokens=32,
            num_beams=4,
            early_stopping=True,
        )

    result = tokenizer.decode(output_ids[0], skip_special_tokens=True).strip().lower()
    logger.debug(f"[RERANKER] input='{input_text}' | generated='{result}'")
    if result in candidates:
        return result
    logger.debug(f"[RERANKER] '{result}' not in candidates, fallback → '{candidates[0]}'")
    return candidates[0]
