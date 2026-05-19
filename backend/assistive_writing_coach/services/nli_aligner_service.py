"""
DeBERTa-v2 NLI contextual aligner.
Premise: original sentence. Hypothesis: sentence with correction applied.
Labels: entailment (0), contradiction (1), neutral (2), off_topic (3).
"""
import logging
import os
import torch
import torch.nn.functional as F
from django.conf import settings
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None

_ID2LABEL = {0: "entailment", 1: "contradiction", 2: "neutral", 3: "off_topic"}


def _load():
    global _model, _tokenizer
    if _model is None:
        model_dir = os.path.join(settings.TRAINED_MODELS_DIR, "nli_model", "final_model")
        _tokenizer = AutoTokenizer.from_pretrained(model_dir)
        _model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        _model.eval()
    return _model, _tokenizer


def align(context: str, corrected_sentence: str) -> dict:
    """
    Returns {'label': str, 'confidence': float, 'scores': dict}.
    Premise is a relevant context window from the reference passage.
    'entailment' means the correction fits the context well.
    """
    model, tokenizer = _load()
    logger.debug(
        f"[NLI]   premise  ({len(context.split())}w): {repr(context[:80])}"
    )
    logger.debug(f"[NLI]   hypothesis: {repr(corrected_sentence[:80])}")

    inputs = tokenizer(
        context,
        corrected_sentence,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = F.softmax(logits, dim=-1)[0]

    pred_id = int(probs.argmax().item())
    label = _ID2LABEL[pred_id]
    confidence = float(probs[pred_id].item())
    scores = {_ID2LABEL[i]: round(float(p.item()), 4) for i, p in enumerate(probs)}

    logger.debug(
        f"[NLI]   result: {label} ({confidence * 100:.1f}%) | raw={scores}"
    )

    return {
        "label": label,
        "confidence": round(confidence, 4),
        "scores": scores,
    }
