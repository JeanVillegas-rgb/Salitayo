"""
classifier.py
-------------
Logistic regression trained on accumulated AttemptLog data.

Label is now GAP-BASED — not binary maintain/regress.
Gap = augmentation_level - initial_augmentation_level (the RR's original decision).

  gap < 0  →  RR over-augmented   (model predicts: reduce augmentation)
  gap = 0  →  RR correct          (model predicts: keep as-is)
  gap > 0  →  RR under-augmented  (model predicts: increase augmentation)

This makes the model learn to CORRECT the Reading Restructurer
rather than replicate it — which is the genuine NLP contribution.

Feature matrix = tabular word state features + PCA-reduced BERT embedding (768→16 dims).
BERT is the NLP layer. sklearn is the decision boundary on top of it.
"""

import os
import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

MODEL_PATH   = os.path.join(os.path.dirname(__file__), "trained_model", "classifier.joblib")
PCA_COMPONENTS = 16


# ------------------------------------------------------------------
# Feature matrix builder
# Tabular features (13 cols) + BERT embedding (768 dims → PCA → 16)
# ------------------------------------------------------------------

TABULAR_FEATURES = [
    "augmentation_level",
    "severity_score",
    "accuracy_rate",
    "recent_accuracy",
    "total_attempts",
    "streak_correct",
    "streak_miss",
    "sessions_since_last_escalation",
    "pos_encoded",
    "syllable_count",
    "word_length",
    "initial_augmentation_level",   # RR's original decision
    "augmentation_gap",             # current correction applied so far
    "frequency_weight",             # escalation/regression urgency signal
]
N_TABULAR = len(TABULAR_FEATURES)   # 14


def build_feature_matrix(word_states, include_embedding: bool = True) -> np.ndarray:
    """
    Converts a list of WordState instances into a numpy feature matrix.

    Columns [0..12]  : tabular features (see TABULAR_FEATURES)
    Columns [13..780]: BERT embedding (768 dims, PCA reduces to 16 later)
    """
    from .models import FeatureExtractor
    
    rows = []
    for ws in word_states:
        fv = FeatureExtractor.from_word_state(ws)
        row = [fv[k] for k in TABULAR_FEATURES]
        if include_embedding and ws.bert_embedding:
            row.extend(ws.bert_embedding)
        elif include_embedding:
            row.extend([0.0] * 768)
        rows.append(row)
    return np.array(rows, dtype=np.float32)


# ------------------------------------------------------------------
# Gap-based label generator
# ------------------------------------------------------------------

def build_labels(word_states) -> np.ndarray:
    """
    Derives gap-based labels from each WordState's current gap value.

    The gap (augmentation_level - initial_augmentation_level) IS the label.
    It tells us how much the Reading Restructurer's decision needed to be
    corrected by real session behavior.

    For the logistic regression we bin the raw gap into 3 classes:
      0  →  RR over-augmented   (gap < 0)  reduce
      1  →  RR correct          (gap = 0)  keep
      2  →  RR under-augmented  (gap > 0)  increase

    Three-class setup allows the model to predict direction AND necessity.
    """
    labels = []
    for ws in word_states:
        gap = ws.augmentation_gap
        if gap < 0:
            labels.append(0)   # over-augmented — RR was too aggressive
        elif gap == 0:
            labels.append(1)   # correct — RR nailed it
        else:
            labels.append(2)   # under-augmented — RR was too conservative
    return np.array(labels, dtype=np.int32)


def gap_label_from_attempt_log(attempt_log) -> int:
    """
    Computes the binned gap label directly from an AttemptLog snapshot.
    Used when backfilling labels into AttemptLog records after a session.
    """
    gap = attempt_log.augmentation_gap_at_attempt
    if gap < 0:
        return 0
    elif gap == 0:
        return 1
    else:
        return 2


# ------------------------------------------------------------------
# Training
# ------------------------------------------------------------------

def train(user_id: int = None, min_samples: int = 20) -> dict:
    """
    Train the logistic regression classifier on accumulated WordState data.

    Args:
        user_id:     Train on one user's data only (per-user model).
                     None = train on all users (global model).
        min_samples: Minimum words with attempts before training.

    Returns:
        dict with metrics, model path, and class distribution.
    """
    from .models import WordState

    qs = WordState.objects.filter(total_attempts__gte=3)
    if user_id:
        qs = qs.filter(user_id=user_id)

    word_states = list(qs)

    if len(word_states) < min_samples:
        return {
            "success": False,
            "reason": f"Insufficient data: {len(word_states)} words with attempts (need {min_samples})",
            "n_samples": len(word_states),
        }

    X_raw = build_feature_matrix(word_states, include_embedding=True)
    y     = build_labels(word_states)

    # Check we have at least 2 classes — can't train otherwise
    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        return {
            "success": False,
            "reason": f"Only one label class present ({unique_classes}). Need more session variance.",
            "n_samples": len(word_states),
        }

    # Split tabular vs embedding columns
    tabular    = X_raw[:, :N_TABULAR]
    embeddings = X_raw[:, N_TABULAR:]

    # PCA on BERT embeddings — reduce 768 → 16
    n_components = min(PCA_COMPONENTS, embeddings.shape[0] - 1, embeddings.shape[1])
    pca = PCA(n_components=n_components)
    embedding_reduced = pca.fit_transform(embeddings)

    X = np.hstack([tabular, embedding_reduced])

    # Train / test split — use train=test on pilot data (< 40 samples)
    if len(X) >= 40:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    clf_pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            class_weight="balanced",   # handles imbalanced gap distribution
            multi_class="multinomial", # 3-class: over / correct / under
            max_iter=1000,
            random_state=42,
        )),
    ])

    clf_pipeline.fit(X_train, y_train)
    y_pred = clf_pipeline.predict(X_test)
    report = classification_report(
        y_test, y_pred,
        target_names=["over_augmented", "correct", "under_augmented"],
        output_dict=True,
    )

    # Class distribution for the research report
    class_dist = {
        "over_augmented":  int(np.sum(y == 0)),
        "correct":         int(np.sum(y == 1)),
        "under_augmented": int(np.sum(y == 2)),
    }

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"pipeline": clf_pipeline, "pca": pca}, MODEL_PATH)

    return {
        "success":               True,
        "n_samples":             len(word_states),
        "n_train":               len(X_train),
        "n_test":                len(X_test),
        "accuracy":              round(report["accuracy"], 3),
        "report":                report,
        "class_distribution":   class_dist,
        "pca_variance_explained": round(float(sum(pca.explained_variance_ratio_)), 3),
        "model_path":            MODEL_PATH,
    }


# ------------------------------------------------------------------
# Inference
# ------------------------------------------------------------------

def load_model() -> dict | None:
    if not os.path.exists(MODEL_PATH):
        return None
    return joblib.load(MODEL_PATH)


def predict(word_state) -> dict:
    """
    Predict the augmentation correction needed for a word.

    Returns:
        {
            "word":           str,
            "predicted_class": int,       # 0=over, 1=correct, 2=under
            "gap_label":      str,        # "over_augmented" | "correct" | "under_augmented"
            "confidence":     float,
            "source":         str,        # "model" | "rule_based"
            "recommendation": str,        # "reduce" | "keep" | "increase"
            "current_gap":    int,        # live gap value from WordState
        }
    """
    LABEL_MAP = {0: "over_augmented", 1: "correct", 2: "under_augmented"}
    ACTION_MAP = {0: "reduce",        1: "keep",    2: "increase"}

    saved = load_model()

    # Rule-based fallback — uses gap directly, no model needed
    if saved is None:
        gap = word_state.augmentation_gap
        if gap < 0:
            cls = 0
        elif gap == 0:
            cls = 1
        else:
            cls = 2

        return {
            "word":            word_state.word,
            "predicted_class": cls,
            "gap_label":       LABEL_MAP[cls],
            "confidence":      1.0,
            "source":          "rule_based",
            "recommendation":  ACTION_MAP[cls],
            "current_gap":     gap,
        }

    clf_pipeline = saved["pipeline"]
    pca          = saved["pca"]

    X_raw             = build_feature_matrix([word_state], include_embedding=True)
    tabular           = X_raw[:, :N_TABULAR]
    embeddings        = X_raw[:, N_TABULAR:]
    embedding_reduced = pca.transform(embeddings)
    X                 = np.hstack([tabular, embedding_reduced])

    cls        = int(clf_pipeline.predict(X)[0])
    proba      = clf_pipeline.predict_proba(X)[0]
    confidence = float(max(proba))

    return {
        "word":            word_state.word,
        "predicted_class": cls,
        "gap_label":       LABEL_MAP[cls],
        "confidence":      round(confidence, 3),
        "source":          "model",
        "recommendation":  ACTION_MAP[cls],
        "current_gap":     word_state.augmentation_gap,
    }


def predict_batch(word_states: list) -> list[dict]:
    return [predict(ws) for ws in word_states]