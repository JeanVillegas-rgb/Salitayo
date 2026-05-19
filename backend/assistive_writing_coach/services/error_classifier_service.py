"""
Loads the RandomForest error classifier and classifies dyslexic error types.
"""
import logging
import os
import joblib
import numpy as np
from django.conf import settings
from .feature_extractor import extract_features

logger = logging.getLogger(__name__)

_model = None

_LABEL_DESCRIPTIONS = {
    "phonetic_sub": "Phonetic Substitution",
    "reversal": "Letter Reversal",
    "omission": "Letter Omission",
    "insertion": "Letter Insertion",
    "transposition": "Letter Transposition",
}


def _get_model():
    global _model
    if _model is None:
        model_path = os.path.join(
            settings.TRAINED_MODELS_DIR,
            "error_classifier",
            "error_classifier.joblib",
        )
        _model = joblib.load(model_path)
    return _model


_FEATURE_NAMES = [
    "raw_edit_distance", "normalized_edit_distance",
    "length_difference_signed", "absolute_length_difference",
    "soundex_equal", "metaphone_equal", "jaro_winkler",
    "bigram_overlap", "trigram_overlap", "positional_match",
    "shared_char_set", "mis_vowel_ratio", "cor_vowel_ratio", "vowel_ratio_diff",
    "misspelled_chars_not_in_correct_ratio",
    "correct_chars_not_in_misspelled_ratio",
    "edit_distance_to_length_diff_ratio",
]


def classify_error(misspelled: str, correct: str) -> dict:
    """
    Returns {'error_type': str, 'label': str, 'confidence': float, 'probabilities': dict}.
    """
    model = _get_model()
    raw_features = extract_features(misspelled, correct)
    features = np.array(raw_features).reshape(1, -1)

    feature_log = "  ".join(
        f"{name}={val:.4f}" for name, val in zip(_FEATURE_NAMES, raw_features)
    )
    logger.debug(f"[CLASSIFIER] '{misspelled}'→'{correct}' features: {feature_log}")

    pred = model.predict(features)[0]
    proba = model.predict_proba(features)[0]
    classes = model.classes_

    prob_map = {cls: float(p) for cls, p in zip(classes, proba)}
    confidence = float(proba.max())

    return {
        "error_type": str(pred),
        "label": _LABEL_DESCRIPTIONS.get(str(pred), str(pred)),
        "confidence": round(confidence, 4),
        "probabilities": {k: round(v, 4) for k, v in prob_map.items()},
    }
