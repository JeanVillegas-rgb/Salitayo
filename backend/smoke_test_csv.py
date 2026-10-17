"""
smoke_test_csv.py  --  SALITAyo Writing Assistant Component Evaluation

Generates five traceable CSV files inside smoke_test_csvs/ that expose
every intermediate computation involved in each NLP model's decision:

  smoke_t5_reranker.csv        -- T5 beam search scores + PASS/FAIL per sample
  smoke_rf_classifier.csv      -- All 17 engineered features + class probabilities per sample
  smoke_rf_per_class_f1.csv    -- Per-class TP / FP / FN / Precision / Recall / F1 / Weight
  smoke_nli_aligner.csv        -- Raw logits + exp(logit) + softmax + formula per pair
  smoke_summary.csv            -- All metric checks with measured vs. threshold vs. status

Run from backend/:
    python smoke_test_csv.py
"""

import os, sys, csv, json, random, math, datetime
from collections import Counter

import numpy as np

# ── Django bootstrap ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salitayo.settings")

import django
django.setup()

import torch
from django.conf import settings
from assistive_writing_coach.services import (
    reranker_service,
    error_classifier_service,
    nli_aligner_service,
)
from assistive_writing_coach.services.feature_extractor import extract_features

# ── Config ────────────────────────────────────────────────────────────────────
RANDOM_SEED   = 42
RERANKER_N    = 30
CLASSIFIER_N  = 30
random.seed(RANDOM_SEED)

MODELS_DIR = str(settings.TRAINED_MODELS_DIR)
OUTPUT_DIR = os.path.join(BASE_DIR, "smoke_test_csvs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CLASSES    = ["phonetic_sub", "reversal", "omission", "insertion", "transposition"]
NLI_LABELS = ["entailment", "contradiction", "neutral", "off_topic"]

# 17 feature column names — must match feature_extractor.extract_features() order
FEAT_COLS = [
    "feat_raw_edit_distance",
    "feat_normalized_edit_distance",
    "feat_length_difference_signed",
    "feat_absolute_length_difference",
    "feat_soundex_equal",
    "feat_metaphone_equal",
    "feat_jaro_winkler_similarity",
    "feat_bigram_overlap_ratio",
    "feat_trigram_overlap_ratio",
    "feat_positional_match_ratio",
    "feat_shared_char_set_ratio",
    "feat_mis_vowel_ratio",
    "feat_cor_vowel_ratio",
    "feat_vowel_ratio_diff",
    "feat_misspelled_chars_not_in_correct_ratio",
    "feat_correct_chars_not_in_misspelled_ratio",
    "feat_edit_dist_to_length_diff_ratio",
]

# ── NLI hand-selected pairs (10 entailment + 10 contradiction) ────────────────
NLI_PAIRS = [
    ("entailment",
     "The student submitted the assignment on time.",
     "The student completed and handed in the task before the deadline."),
    ("entailment",
     "She felt tired after the long journey through the mountains.",
     "She was exhausted from traveling a great distance."),
    ("entailment",
     "The teacher explained the concept clearly to the whole class.",
     "The instructor made the topic easy to understand for the students."),
    ("entailment",
     "He bought a new laptop computer specifically for his university studies.",
     "He purchased a device to help with his academic work."),
    ("entailment",
     "The library has an extensive collection of books on science and technology.",
     "Scientific literature is available for borrowing at the library."),
    ("entailment",
     "They arrived at the airport two full hours before their departure time.",
     "They reached the terminal well ahead of their scheduled flight."),
    ("entailment",
     "The construction project was completed three months ahead of schedule.",
     "The team finished the building work earlier than originally planned."),
    ("entailment",
     "She enjoyed reading novels and short stories during her free time.",
     "She liked spending her leisure hours engaged with books."),
    ("entailment",
     "The scientific experiment produced several unexpected and novel results.",
     "The findings from the laboratory test were surprising to the researchers."),
    ("entailment",
     "He trained rigorously every single day to improve his athletic performance.",
     "He practiced on a daily basis in order to become better at his sport."),
    ("contradiction",
     "The patient made a full recovery after the successful surgical procedure.",
     "The patient did not survive the operation and died on the table."),
    ("contradiction",
     "The convenience store remains open twenty-four hours a day, seven days a week.",
     "The shop closes at six in the evening and does not open on weekends."),
    ("contradiction",
     "She consistently excelled in mathematics and received top marks throughout school.",
     "She always struggled with numbers and repeatedly failed her math examinations."),
    ("contradiction",
     "The weather was sunny, warm, and absolutely perfect for an outdoor picnic.",
     "Heavy rain and strong winds ruined all plans for outdoor activities that day."),
    ("contradiction",
     "He made the bold decision to quit his stable job and launch his own business.",
     "He chose to remain safely at his current company and avoid taking any risks."),
    ("contradiction",
     "The impressive skyscraper was constructed in under twelve months.",
     "It took several decades and multiple generations of workers to complete the building."),
    ("contradiction",
     "The home team lost every single game in the entire tournament.",
     "The home team won the championship without dropping a single match."),
    ("contradiction",
     "She became the youngest person in history to receive the prestigious national award.",
     "Only candidates above the age of sixty were eligible to receive the prize."),
    ("contradiction",
     "The river bed was completely dry and cracked during the prolonged drought.",
     "The river burst its banks and flooded the surrounding towns and farmland."),
    ("contradiction",
     "Both parties mutually agreed to meet face to face at noon in the central park.",
     "Each side refused all contact and remained in their respective homes."),
]

# ── Data loaders ──────────────────────────────────────────────────────────────

def _load_reranker_samples(n):
    path = os.path.join(MODELS_DIR, "reranker", "test_results_for_excel.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    random.shuffle(rows)
    return rows[:n]

def _load_classifier_samples(n):
    path = os.path.join(MODELS_DIR, "error_classifier", "test_results_for_excel.csv")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    random.shuffle(rows)
    return rows[:n]

# ── T5 Reranker inference with beam score tracing ─────────────────────────────

def run_reranker(samples):
    """
    Runs T5 beam-search generation with return_dict_in_generate=True so that
    sequences_scores (length-normalised sum-of-log-probs) are captured.

    sequences_scores formula:
        score = sum(log P(token_t | token_0..t-1, input)) / num_generated_tokens
    Geometric-mean per-token probability = exp(score)
    This is NOT the joint probability of the full sequence; it is the per-token
    average, which gives a model-confidence proxy comparable across different
    output lengths.
    """
    model, tokenizer = reranker_service._load()
    results = []

    for i, row in enumerate(samples, 1):
        misspelled  = row["misspelled_word"]
        correct     = row["correct_word"]
        candidates  = [c.strip() for c in row["candidates_shown"].split(",")]
        cand_str    = " | ".join(candidates)
        input_text  = f"correct: {misspelled} options: {cand_str}"

        inputs = tokenizer(input_text, return_tensors="pt",
                           max_length=128, truncation=True)

        with torch.no_grad():
            out = model.generate(
                inputs["input_ids"],
                max_new_tokens=32,
                num_beams=4,
                early_stopping=True,
                return_dict_in_generate=True,
                output_scores=True,
            )

        predicted_raw = tokenizer.decode(
            out.sequences[0], skip_special_tokens=True
        ).strip().lower()

        # Beam score: length-normalised log-probability of the winning sequence.
        # out.sequences_scores is available because output_scores=True.
        seq_log_prob = float(out.sequences_scores[0])
        geo_mean_prob = math.exp(seq_log_prob)

        # Production fallback: if decoded token is not in candidates use candidates[0]
        if predicted_raw in candidates:
            predicted = predicted_raw
            fallback_applied = "NO"
        else:
            predicted = candidates[0]
            fallback_applied = "YES"

        match   = predicted.strip().lower() == correct.strip().lower()
        in_cand = correct.lower() in [c.lower() for c in candidates]

        note = ""
        if not in_cand:
            note = "Correct word absent from candidates; model cannot recover regardless of reranking."
        elif fallback_applied == "YES":
            note = f"T5 decoded '{predicted_raw}' (not in candidates); production fallback applied to candidates[0]."

        results.append({
            "sample_id":                     f"RR-{i:03d}",
            "misspelled_word":               misspelled,
            "correct_word":                  correct,
            "num_candidates":                len(candidates),
            "candidates_shown":              "; ".join(candidates),
            "t5_input_string":               input_text,
            "model_raw_decoded_output":      predicted_raw,
            "fallback_to_candidates0":       fallback_applied,
            "final_predicted_word":          predicted,
            # ── Beam search score tracing ──────────────────────────────────
            "beam_sequence_log_prob":        round(seq_log_prob, 6),
            "beam_score_formula":            (
                f"score = sum(log P(token_t|context)) / num_tokens  "
                f"=> {seq_log_prob:.6f}"
            ),
            "geometric_mean_token_prob":     round(geo_mean_prob, 6),
            "geometric_mean_token_prob_pct": f"{geo_mean_prob * 100:.2f}%",
            "geo_mean_formula":              (
                f"exp(beam_score) = exp({seq_log_prob:.6f}) = {geo_mean_prob:.6f}"
            ),
            "score_interpretation":          (
                "Higher (less negative) log-prob = model assigns higher average "
                "per-token probability to the winning beam sequence."
            ),
            # ── Decision ───────────────────────────────────────────────────
            "correct_in_candidates":         "YES" if in_cand else "NO",
            "top1_correct":                  "PASS" if match else "FAIL",
            "notes":                         note,
        })

        print(f"    {i:>2}/{RERANKER_N}  {misspelled!r:20} -> {predicted!r}"
              f"  (correct={correct!r})  log_p={seq_log_prob:.4f}")

    return results

# ── RF Classifier inference with feature + probability tracing ────────────────

def run_classifier(samples):
    """
    Extracts all 17 hand-engineered features and calls predict_proba().

    RandomForest confidence = fraction of decision trees that voted for the
    winning class:
        P(class_c | x) = (# trees voting for c) / (# total trees)

    The 17 features span four signal groups:
        Edit distance  : raw_edit_distance, normalized_edit_distance,
                         length_difference_signed, absolute_length_difference
        Phonetic       : soundex_equal, metaphone_equal, jaro_winkler_similarity
        N-gram overlap : bigram_overlap_ratio, trigram_overlap_ratio
        Character/vowel: positional_match_ratio, shared_char_set_ratio,
                         mis_vowel_ratio, cor_vowel_ratio, vowel_ratio_diff,
                         misspelled_chars_not_in_correct_ratio,
                         correct_chars_not_in_misspelled_ratio,
                         edit_dist_to_length_diff_ratio
    """
    clf = error_classifier_service._get_model()
    results = []

    for i, row in enumerate(samples, 1):
        misspelled = row["misspelled_word"]
        correct    = row["correct_word"]
        true_type  = row["true_error_type"]

        feats  = extract_features(misspelled, correct)  # list of 17 floats
        proba  = clf.predict_proba([feats])[0]          # shape (5,)
        classes = list(clf.classes_)
        prob_map = {cls: float(p) for cls, p in zip(classes, proba)}
        predicted = str(clf.predict([feats])[0])
        confidence = max(prob_map.values())

        # RF vote formula: fraction of trees that voted for winning class
        n_trees = clf.n_estimators
        n_voted = round(confidence * n_trees)
        rf_formula = (
            f"P({predicted}) = {n_voted} / {n_trees} trees"
            f" = {confidence:.6f}"
        )

        r = {
            "sample_id":         row["sample_id"],
            "misspelled_word":   misspelled,
            "correct_word":      correct,
            "true_error_type":   true_type,
            "predicted_error_type": predicted,
        }
        for fname, fval in zip(FEAT_COLS, feats):
            r[fname] = round(fval, 6)

        for cls in CLASSES:
            r[f"prob_{cls}"] = round(prob_map.get(cls, 0.0), 6)

        r["confidence"]              = round(confidence, 6)
        r["confidence_pct"]          = f"{confidence * 100:.2f}%"
        r["rf_vote_formula"]         = rf_formula
        r["confidence_interpretation"] = (
            "Fraction of the RandomForest's decision trees that voted for "
            "the predicted class. A value of 1.0 means unanimous agreement."
        )
        r["pass_fail"] = "PASS" if predicted == true_type else "FAIL"

        results.append(r)
        print(f"    {i:>2}/{CLASSIFIER_N}  {misspelled!r:20} -> {predicted!r}"
              f"  (true={true_type!r})  conf={confidence:.4f}")

    return results

# ── DeBERTa NLI inference with full logit / softmax tracing ──────────────────

def run_nli():
    """
    Exposes every step of the softmax confidence computation:

        1. Model outputs raw logit scores  z_i  for each class i.
        2. Softmax converts to probabilities:
               P(class_i) = exp(z_i) / sum_j(exp(z_j))
        3. The predicted class = argmax P(class_i).
        4. Confidence = P(predicted_class) = max softmax probability.

    Numerical-stability note: we subtract max(z) before taking exp.
    This does NOT change the final softmax values (cancels in numerator
    and denominator) but prevents floating-point overflow.

        P(class_i) = exp(z_i - z_max) / sum_j(exp(z_j - z_max))
    """
    nli_aligner_service._load()
    nli_model     = nli_aligner_service._model
    nli_tokenizer = nli_aligner_service._tokenizer

    ID2LABEL = {0: "entailment", 1: "contradiction", 2: "neutral", 3: "off_topic"}

    results = []
    for i, (expected, premise, hypothesis) in enumerate(NLI_PAIRS, 1):
        inputs = nli_tokenizer(
            premise, hypothesis,
            return_tensors="pt", truncation=True, max_length=512,
        )
        with torch.no_grad():
            logits = nli_model(**inputs).logits[0].cpu().numpy()  # shape (4,)

        # ── Softmax computation ───────────────────────────────────────────
        z_max     = logits.max()                    # for numerical stability
        shifted   = logits - z_max                  # z_i - z_max
        exp_vals  = np.exp(shifted)                 # exp(z_i - z_max)
        sum_exp   = exp_vals.sum()                  # denominator
        probs     = exp_vals / sum_exp              # final softmax P(class_i)

        pred_id    = int(probs.argmax())
        pred_label = ID2LABEL[pred_id]
        confidence = float(probs[pred_id])

        # Human-readable formula for the predicted class
        terms = " + ".join(
            f"exp({logits[j]:.4f} - {z_max:.4f})"
            for j in range(4)
        )
        num = f"exp({logits[pred_id]:.4f} - {z_max:.4f})"
        softmax_formula = (
            f"P({pred_label}) = {num} / [{terms}]"
            f" = {exp_vals[pred_id]:.6f} / {sum_exp:.6f}"
            f" = {confidence:.6f}"
        )

        r = {
            "pair_id":        f"NLI-{i:02d}",
            "expected_class": expected,
            "premise":        premise,
            "hypothesis":     hypothesis,
            # raw logits from DeBERTa linear head
            "logit_entailment":    round(float(logits[0]), 6),
            "logit_contradiction": round(float(logits[1]), 6),
            "logit_neutral":       round(float(logits[2]), 6),
            "logit_off_topic":     round(float(logits[3]), 6),
            # z_max used for numerical stability
            "z_max_for_stability": round(float(z_max), 6),
            # shifted logits = z_i - z_max
            "shifted_logit_entailment":    round(float(shifted[0]), 6),
            "shifted_logit_contradiction": round(float(shifted[1]), 6),
            "shifted_logit_neutral":       round(float(shifted[2]), 6),
            "shifted_logit_off_topic":     round(float(shifted[3]), 6),
            # exp(shifted logit) = numerator before normalisation
            "exp_entailment":    round(float(exp_vals[0]), 6),
            "exp_contradiction": round(float(exp_vals[1]), 6),
            "exp_neutral":       round(float(exp_vals[2]), 6),
            "exp_off_topic":     round(float(exp_vals[3]), 6),
            # denominator
            "sum_of_exp":        round(float(sum_exp), 6),
            # final softmax probabilities
            "softmax_entailment":    round(float(probs[0]), 6),
            "softmax_contradiction": round(float(probs[1]), 6),
            "softmax_neutral":       round(float(probs[2]), 6),
            "softmax_off_topic":     round(float(probs[3]), 6),
            # formula trace for the winning class
            "softmax_formula_predicted_class": softmax_formula,
            # decision
            "predicted_class":       pred_label,
            "confidence":            round(confidence, 6),
            "confidence_pct":        f"{confidence * 100:.2f}%",
            "correct":               "PASS" if pred_label == expected else "FAIL",
        }
        results.append(r)
        print(f"    {i:>2}/20  expected={expected:>15}  predicted={pred_label:>15}"
              f"  conf={confidence * 100:.1f}%")

    return results

# ── Per-class F1 breakdown (RF classifier) ────────────────────────────────────

def compute_per_class_f1(clf_results):
    """
    For each of the 5 error-type classes compute:
        TP  = true positives
        FP  = false positives (predicted as class, was something else)
        FN  = false negatives (was class, predicted as something else)
        Precision = TP / (TP + FP)
        Recall    = TP / (TP + FN)
        F1        = 2 * P * R / (P + R)
        Support   = number of true instances of this class
        Weight    = Support / total
        Weighted_contribution = F1 * Weight
    """
    true_labels = [r["true_error_type"]      for r in clf_results]
    pred_labels = [r["predicted_error_type"] for r in clf_results]
    support     = Counter(true_labels)
    total       = len(true_labels)

    rows = []
    wf1_total = 0.0
    for cls in CLASSES:
        tp  = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p == cls)
        fp  = sum(1 for t, p in zip(true_labels, pred_labels) if t != cls and p == cls)
        fn  = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p != cls)
        sup = support[cls]

        pre = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1  = 2 * pre * rec  / (pre + rec) if (pre + rec) > 0 else 0.0
        wgt = sup / total if total > 0 else 0.0
        wcontrib = f1 * wgt
        wf1_total += wcontrib

        rows.append({
            "error_type":            cls,
            "TP":                    tp,
            "FP":                    fp,
            "FN":                    fn,
            "precision":             round(pre, 6),
            "precision_formula":     f"TP/(TP+FP) = {tp}/({tp}+{fp}) = {pre:.6f}",
            "recall":                round(rec, 6),
            "recall_formula":        f"TP/(TP+FN) = {tp}/({tp}+{fn}) = {rec:.6f}",
            "f1_score":              round(f1, 6),
            "f1_formula":            (
                f"2*P*R/(P+R) = 2*{pre:.4f}*{rec:.4f}/({pre:.4f}+{rec:.4f}) = {f1:.6f}"
            ),
            "support_n":             sup,
            "weight":                round(wgt, 6),
            "weight_formula":        f"support / total = {sup} / {total} = {wgt:.6f}",
            "weighted_f1_contrib":   round(wcontrib, 6),
            "weighted_contrib_formula": (
                f"F1 * weight = {f1:.4f} * {wgt:.4f} = {wcontrib:.6f}"
            ),
        })

    # Totals row
    rows.append({
        "error_type":            "TOTAL / WEIGHTED F1",
        "TP":                    sum(r["TP"] for r in rows),
        "FP":                    sum(r["FP"] for r in rows),
        "FN":                    sum(r["FN"] for r in rows),
        "precision":             "",
        "precision_formula":     "",
        "recall":                "",
        "recall_formula":        "",
        "f1_score":              "",
        "f1_formula":            "",
        "support_n":             total,
        "weight":                1.0,
        "weight_formula":        "",
        "weighted_f1_contrib":   round(wf1_total, 6),
        "weighted_contrib_formula": (
            "sum(F1_i * weight_i) for all 5 classes = "
            f"{round(wf1_total, 6)}"
        ),
    })
    return rows, wf1_total

# ── Summary CSV ───────────────────────────────────────────────────────────────

def build_summary(rer_results, clf_results, nli_results,
                  wf1_smoke, rer_metrics, clf_metrics):

    rer_acc    = sum(1 for r in rer_results if r["top1_correct"] == "PASS") / len(rer_results)
    nli_correct = sum(1 for r in nli_results if r["correct"] == "PASS")
    nli_acc    = nli_correct / len(nli_results)
    nli_conf   = sum(r["confidence"] for r in nli_results) / len(nli_results)
    nli_conf_ent = (
        sum(r["confidence"] for r in nli_results if r["expected_class"] == "entailment") / 10
    )
    nli_conf_con = (
        sum(r["confidence"] for r in nli_results if r["expected_class"] == "contradiction") / 10
    )

    def _row(component, metric, smoke_val, smoke_val_fmt,
             threshold, direction, full_val, full_val_fmt,
             status, notes=""):
        return {
            "component":          component,
            "metric":             metric,
            "smoke_test_value":   smoke_val_fmt,
            "threshold":          threshold,
            "direction":          direction,
            "full_test_set_value": full_val_fmt,
            "status":             status,
            "notes":              notes,
        }

    rows = [
        # ── T5 Reranker ──────────────────────────────────────────────────
        _row("T5-small Reranker",
             "Top-1 Accuracy (smoke, n=30)",
             rer_acc, f"{rer_acc:.4f} ({rer_acc*100:.2f}%)",
             ">=0.85 (85%)", ">=",
             rer_metrics["top1_accuracy_on_test_set"],
             f"{rer_metrics['top1_accuracy_on_test_set']:.4f} "
             f"({rer_metrics['top1_accuracy_on_test_set']*100:.2f}%)",
             "PASS" if rer_acc >= 0.85 else "FAIL",
             f"Smoke subset: {sum(1 for r in rer_results if r['top1_correct']=='PASS')} / {len(rer_results)} correct. "
             f"Full test set: {rer_metrics['number_of_test_samples']} samples."),

        _row("T5-small Reranker",
             "Baseline comparison (SymSpell candidates[0])",
             "", "N/A -- not re-run in smoke test",
             "~72-75% (literature)", "Reranker improves over",
             "~72-75% (Flor et al.)", "~72-75%",
             "REFERENCE",
             "SymSpell frequency-ranked baseline: top-1 without reranking. "
             "Reranker at 85.77% represents approx +10-13 pp improvement."),

        # ── RF Classifier ─────────────────────────────────────────────────
        _row("RF Error Classifier",
             "Weighted F1 (smoke, n=30)",
             wf1_smoke, f"{wf1_smoke:.4f} ({wf1_smoke*100:.2f}%)",
             ">=0.95 (95%)", ">=",
             clf_metrics["test_f1_weighted"],
             f"{clf_metrics['test_f1_weighted']:.4f} "
             f"({clf_metrics['test_f1_weighted']*100:.2f}%)",
             "PASS" if wf1_smoke >= 0.95 else "FAIL",
             "See smoke_rf_per_class_f1.csv for per-class TP/FP/FN breakdown."),

        _row("RF Error Classifier",
             "Unseen Pair Accuracy (full test set)",
             None, "N/A -- full test set metric only",
             ">=0.70 (70%)", ">=",
             clf_metrics["unseen_pair_accuracy"],
             f"{clf_metrics['unseen_pair_accuracy']:.4f} "
             f"({clf_metrics['unseen_pair_accuracy']*100:.2f}%)",
             "PASS" if clf_metrics["unseen_pair_accuracy"] >= 0.70 else "FAIL",
             "Evaluated on (misspelled, correct) pairs never seen before or after SMOTE. "
             "Lower floor (0.70) reflects expected out-of-distribution degradation."),

        _row("RF Error Classifier",
             "Majority-class baseline (reference)",
             "", "N/A",
             "0.60-0.65 (pre-SMOTE)", "Classifier improves over",
             "~0.60-0.65", "~0.60-0.65",
             "REFERENCE",
             "Weighted F1 if all samples predicted as majority class on imbalanced "
             "pre-SMOTE dataset. Classifier at 98.09% WF1 represents approx +33 pp."),

        # ── DeBERTa NLI ──────────────────────────────────────────────────
        _row("DeBERTa-v2 NLI",
             "Mean softmax confidence (20 hand-selected pairs)",
             nli_conf, f"{nli_conf:.4f} ({nli_conf*100:.2f}%)",
             ">=0.70 (70%)", ">=",
             "N/A (smoke-test-only metric)",
             "N/A",
             "PASS" if nli_conf >= 0.70 else "FAIL",
             f"Mean over all 20 pairs. "
             f"Entailment pairs: {nli_conf_ent:.4f}. "
             f"Contradiction pairs: {nli_conf_con:.4f}. "
             "See smoke_nli_aligner.csv for per-pair logit/softmax trace."),

        _row("DeBERTa-v2 NLI",
             "Mean confidence -- 10 entailment pairs",
             nli_conf_ent, f"{nli_conf_ent:.4f} ({nli_conf_ent*100:.2f}%)",
             ">=0.70 (component of overall threshold)", ">=",
             "N/A", "N/A",
             "PASS" if nli_conf_ent >= 0.70 else "FAIL", ""),

        _row("DeBERTa-v2 NLI",
             "Mean confidence -- 10 contradiction pairs",
             nli_conf_con, f"{nli_conf_con:.4f} ({nli_conf_con*100:.2f}%)",
             ">=0.70 (component of overall threshold)", ">=",
             "N/A", "N/A",
             "PASS" if nli_conf_con >= 0.70 else "FAIL", ""),

        _row("DeBERTa-v2 NLI",
             "Classification accuracy on 20 smoke pairs",
             nli_acc, f"{nli_acc:.4f} ({nli_acc*100:.2f}%)",
             "No threshold -- descriptive", "Descriptive",
             "91.1% (MNLI, He et al. 2021)",
             "91.1%",
             "REFERENCE",
             f"Correctly classified {nli_correct}/20 smoke pairs. "
             "Reported descriptively vs. MNLI benchmark; no independent threshold "
             "set to avoid circular replication or arbitrary floor."),
    ]
    return rows

# ── CSV writer helper ─────────────────────────────────────────────────────────

def _write(filename, rows, fieldnames):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames,
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    size_kb = os.path.getsize(path) / 1024
    print(f"  -> {filename}  ({size_kb:.1f} KB,  {len(rows)} data rows)")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    SEP = "=" * 70
    ts  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{SEP}")
    print(f"SALITAyo -- Model Evaluation Smoke Test (CSV output)")
    print(f"Started: {ts}")
    print(SEP)

    # Full-evaluation metrics (pre-computed, stored with models)
    with open(os.path.join(MODELS_DIR, "reranker",
                           "final_model", "evaluation_metrics.json")) as f:
        rer_metrics = json.load(f)
    with open(os.path.join(MODELS_DIR, "error_classifier",
                           "training_metadata.json")) as f:
        clf_metrics = json.load(f)

    # ── Run inference ─────────────────────────────────────────────────────────
    print(f"\n[1/3] T5-small Reranker  (n={RERANKER_N})")
    rer_samples = _load_reranker_samples(RERANKER_N)
    rer_results = run_reranker(rer_samples)

    print(f"\n[2/3] RF Error Classifier  (n={CLASSIFIER_N})")
    clf_samples = _load_classifier_samples(CLASSIFIER_N)
    clf_results = run_classifier(clf_samples)

    print(f"\n[3/3] DeBERTa-v2 NLI Aligner  (n=20 hand-selected pairs)")
    nli_results = run_nli()

    # ── Per-class F1 (from smoke-test samples) ────────────────────────────────
    per_class_rows, wf1_smoke = compute_per_class_f1(clf_results)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_rows = build_summary(
        rer_results, clf_results, nli_results,
        wf1_smoke, rer_metrics, clf_metrics,
    )

    # ── Write CSVs ────────────────────────────────────────────────────────────
    print(f"\nWriting CSVs to  {OUTPUT_DIR} ...")

    # 1. T5 Reranker
    _write(
        "smoke_t5_reranker.csv",
        rer_results,
        [
            "sample_id", "misspelled_word", "correct_word",
            "num_candidates", "candidates_shown", "t5_input_string",
            "model_raw_decoded_output", "fallback_to_candidates0",
            "final_predicted_word",
            "beam_sequence_log_prob", "beam_score_formula",
            "geometric_mean_token_prob", "geometric_mean_token_prob_pct",
            "geo_mean_formula", "score_interpretation",
            "correct_in_candidates", "top1_correct", "notes",
        ],
    )

    # 2. RF Classifier (all 17 features + class probs)
    clf_fields = (
        ["sample_id", "misspelled_word", "correct_word",
         "true_error_type", "predicted_error_type"]
        + FEAT_COLS
        + [f"prob_{c}" for c in CLASSES]
        + ["confidence", "confidence_pct",
           "rf_vote_formula", "confidence_interpretation", "pass_fail"]
    )
    _write("smoke_rf_classifier.csv", clf_results, clf_fields)

    # 3. Per-class F1 breakdown
    _write(
        "smoke_rf_per_class_f1.csv",
        per_class_rows,
        [
            "error_type", "TP", "FP", "FN",
            "precision", "precision_formula",
            "recall", "recall_formula",
            "f1_score", "f1_formula",
            "support_n", "weight", "weight_formula",
            "weighted_f1_contrib", "weighted_contrib_formula",
        ],
    )

    # 4. DeBERTa NLI (logits + softmax trace)
    _write(
        "smoke_nli_aligner.csv",
        nli_results,
        [
            "pair_id", "expected_class", "premise", "hypothesis",
            "logit_entailment", "logit_contradiction",
            "logit_neutral", "logit_off_topic",
            "z_max_for_stability",
            "shifted_logit_entailment", "shifted_logit_contradiction",
            "shifted_logit_neutral", "shifted_logit_off_topic",
            "exp_entailment", "exp_contradiction",
            "exp_neutral", "exp_off_topic",
            "sum_of_exp",
            "softmax_entailment", "softmax_contradiction",
            "softmax_neutral", "softmax_off_topic",
            "softmax_formula_predicted_class",
            "predicted_class", "confidence", "confidence_pct", "correct",
        ],
    )

    # 5. Summary
    _write(
        "smoke_summary.csv",
        summary_rows,
        ["component", "metric", "smoke_test_value", "threshold",
         "direction", "full_test_set_value", "status", "notes"],
    )

    print(f"\n{SEP}")
    print("All files written.  Open smoke_test_csvs/ to review results.")
    print(SEP + "\n")


if __name__ == "__main__":
    main()
