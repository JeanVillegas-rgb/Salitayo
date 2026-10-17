"""
smoke_test_eval.py — SALITAyo Writing Assistant Component Evaluation

Evaluates all three trained models at the component level and writes a
traceable Excel workbook to smoke_test_results.xlsx.

Run from backend/:
    python smoke_test_eval.py
"""

import os, sys, csv, json, random, datetime
from collections import Counter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salitayo.settings")

import django
django.setup()

from django.conf import settings
from assistive_writing_coach.services import (
    reranker_service,
    error_classifier_service,
    nli_aligner_service,
)

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Config ────────────────────────────────────────────────────────────────────
RANDOM_SEED  = 42
RERANKER_N   = 30
CLASSIFIER_N = 30
random.seed(RANDOM_SEED)

MODELS_DIR = str(settings.TRAINED_MODELS_DIR)

# ── Palette ───────────────────────────────────────────────────────────────────
DARK_NAVY   = "1F3864"
MID_BLUE    = "2E75B6"
LIGHT_BLUE  = "D6E4F7"
PASS_GREEN  = "E2EFDA"
FAIL_RED    = "FCE4D6"
DARK_GREEN  = "375623"
DARK_RED    = "C00000"
SUBHDR_GRAY = "D9D9D9"
SECTION_HDR = "203864"
ROW_ALT     = "F5F9FF"

# ── Style helpers ─────────────────────────────────────────────────────────────

def _thin_border():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)

def _center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)

def _left_wrap():
    return Alignment(horizontal="left", vertical="center", wrap_text=True)

def _apply_header(ws, row, texts, bg=MID_BLUE, fg="FFFFFF", start_col=1):
    for i, text in enumerate(texts):
        c = ws.cell(row=row, column=start_col + i, value=text)
        c.font = Font(bold=True, size=10, color=fg)
        c.fill = PatternFill("solid", fgColor=bg)
        c.alignment = _center()
        c.border = _thin_border()
    ws.row_dimensions[row].height = 28

def _section_title(ws, row, text, n_cols):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=n_cols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(bold=True, size=11, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=MID_BLUE)
    c.alignment = _center()
    ws.row_dimensions[row].height = 24
    return row + 1

def _info_row(ws, row, label, value, n_cols=8):
    ws.cell(row=row, column=1, value=label).font = Font(bold=True, size=10)
    ws.cell(row=row, column=1).fill = PatternFill("solid", fgColor=SUBHDR_GRAY)
    ws.cell(row=row, column=1).alignment = _left_wrap()
    ws.cell(row=row, column=1).border = _thin_border()
    ws.cell(row=row, column=2, value=value).font = Font(size=10)
    ws.cell(row=row, column=2).alignment = _left_wrap()
    ws.cell(row=row, column=2).border = _thin_border()
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=n_cols)
    ws.row_dimensions[row].height = 18

def _summary_row(ws, row, label, value, fmt=None, is_status=False, n_cols=8):
    c1 = ws.cell(row=row, column=1, value=label)
    c1.font = Font(bold=True, size=10)
    c1.fill = PatternFill("solid", fgColor=SUBHDR_GRAY)
    c1.alignment = _left_wrap()
    c1.border = _thin_border()

    c2 = ws.cell(row=row, column=2, value=value)
    c2.font = Font(bold=is_status, size=10,
                   color=(DARK_GREEN if is_status and "PASS" in str(value)
                          else DARK_RED if is_status else "000000"))
    if fmt:
        c2.number_format = fmt
    if is_status:
        c2.fill = PatternFill("solid", fgColor=(
            PASS_GREEN if "PASS" in str(value) else FAIL_RED))
    c2.alignment = _center()
    c2.border = _thin_border()
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=n_cols)
    ws.row_dimensions[row].height = 18

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

# ── Hand-selected NLI pairs (10 entailment + 10 contradiction) ────────────────
# Pairs are unambiguous so the model should be highly confident.
NLI_PAIRS = [
    # ── ENTAILMENT (correct sentence fits/elaborates the context) ──
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
    # ── CONTRADICTION (corrected sentence contradicts the context) ──
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

# ── Inference ─────────────────────────────────────────────────────────────────

def _run_reranker(samples):
    print(f"  [T5 Reranker] Running live inference on {len(samples)} samples ...")
    results = []
    for i, row in enumerate(samples, 1):
        misspelled = row["misspelled_word"]
        correct    = row["correct_word"]
        candidates = [c.strip() for c in row["candidates_shown"].split(",")]
        print(f"    {i:>2}/{len(samples)}  {misspelled!r:20} -> candidates: {candidates}")
        predicted = reranker_service.rerank(misspelled, candidates)
        match = predicted.strip().lower() == correct.strip().lower()
        in_cands = correct.lower() in [c.lower() for c in candidates]
        results.append({
            "misspelled":  misspelled,
            "correct":     correct,
            "candidates":  ", ".join(candidates),
            "predicted":   predicted,
            "match":       "PASS" if match else "FAIL",
            "in_cands":    "YES"  if in_cands else "NO",
        })
    return results


def _run_classifier(samples):
    print(f"  [RF Classifier] Running live inference on {len(samples)} samples ...")
    results = []
    for i, row in enumerate(samples, 1):
        misspelled = row["misspelled_word"]
        correct    = row["correct_word"]
        true_type  = row["true_error_type"]
        print(f"    {i:>2}/{len(samples)}  {misspelled!r:20} -> {correct!r}  (true: {true_type})")
        out = error_classifier_service.classify_error(misspelled, correct)
        predicted = out["error_type"]
        results.append({
            "sample_id":  row["sample_id"],
            "misspelled": misspelled,
            "correct":    correct,
            "true_type":  true_type,
            "predicted":  predicted,
            "confidence": out["confidence"],
            "match":      "PASS" if predicted == true_type else "FAIL",
        })
    return results


def _run_nli():
    print(f"  [DeBERTa NLI] Running live inference on {len(NLI_PAIRS)} hand-selected pairs ...")
    results = []
    for i, (expected, premise, hyp) in enumerate(NLI_PAIRS, 1):
        print(f"    {i:>2}/{len(NLI_PAIRS)}  expected={expected}")
        out = nli_aligner_service.align(premise, hyp)
        results.append({
            "pair_id":    f"NLI-{i:02d}",
            "expected":   expected,
            "premise":    premise,
            "hypothesis": hyp,
            "predicted":  out["label"],
            "confidence": out["confidence"],
            "scores":     out["scores"],
            "match":      "PASS" if out["label"] == expected else "FAIL",
        })
    return results

# ── Python-side weighted F1 (for summary dashboard only) ─────────────────────

def _weighted_f1(true_labels, pred_labels, classes):
    support = Counter(true_labels)
    total   = len(true_labels)
    if total == 0:
        return 0.0
    wf1 = 0.0
    for cls in classes:
        tp  = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p == cls)
        fp  = sum(1 for t, p in zip(true_labels, pred_labels) if t != cls and p == cls)
        fn  = sum(1 for t, p in zip(true_labels, pred_labels) if t == cls and p != cls)
        pre = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1  = 2 * pre * rec / (pre + rec) if (pre + rec) > 0 else 0.0
        wf1 += f1 * (support[cls] / total)
    return wf1

# ── Sheet 1: Summary Dashboard ────────────────────────────────────────────────

def _write_summary(wb, reranker_res, classifier_res, nli_res,
                   rer_metrics, clf_metrics):
    ws = wb.create_sheet("Summary Dashboard", 0)
    N = 7  # number of columns

    # Title
    ws.merge_cells(f"A1:G1")
    c = ws["A1"]
    c.value = "SALITAyo Writing Assistant — Model Evaluation Smoke Test"
    c.font  = Font(bold=True, size=16, color="FFFFFF")
    c.fill  = PatternFill("solid", fgColor=DARK_NAVY)
    c.alignment = _center()
    ws.row_dimensions[1].height = 36

    ws.merge_cells("A2:G2")
    c = ws["A2"]
    c.value = (f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
               f"   |   Random seed: {RANDOM_SEED}"
               f"   |   Reranker sample n={RERANKER_N}   Classifier sample n={CLASSIFIER_N}"
               f"   |   NLI pairs n=20")
    c.font = Font(italic=True, size=9, color="595959")
    c.alignment = _center()
    ws.row_dimensions[2].height = 16

    row = 4
    _apply_header(ws, row,
                  ["Component", "Metric", "Smoke-Test Value",
                   "Threshold", "Dir.", "Full Test-Set Value", "Status"])
    row += 1

    # Pre-compute Python-side values
    r_acc   = sum(1 for r in reranker_res  if r["match"] == "PASS") / len(reranker_res)
    c_wf1   = _weighted_f1([r["true_type"]  for r in classifier_res],
                           [r["predicted"]  for r in classifier_res],
                           ["phonetic_sub","reversal","omission","insertion","transposition"])
    n_acc   = sum(1 for r in nli_res if r["match"] == "PASS") / len(nli_res)
    n_conf  = sum(r["confidence"] for r in nli_res) / len(nli_res)

    rows_data = [
        # (component, metric, smoke_val, threshold, dir_label, full_val, val_fmt, pass_bool)
        ("T5-small Reranker",
         "Top-1 Accuracy",
         r_acc,  0.85, "≥",
         rer_metrics["top1_accuracy_on_test_set"],
         "0.00%",
         r_acc >= 0.85,
         rer_metrics["top1_accuracy_on_test_set"] >= 0.85),

        ("RF Error Classifier",
         "Weighted F1 Score",
         c_wf1, 0.95, "≥",
         clf_metrics["test_f1_weighted"],
         "0.0000",
         c_wf1 >= 0.95,
         clf_metrics["test_f1_weighted"] >= 0.95),

        ("RF Error Classifier",
         "Unseen Pair Accuracy",
         None,  0.70, "≥",
         clf_metrics["unseen_pair_accuracy"],
         "0.0000",
         None,
         clf_metrics["unseen_pair_accuracy"] >= 0.70),

        ("DeBERTa-v2 NLI",
         "Mean Softmax Confidence (20 pairs)",
         n_conf, 0.70, "≥",
         "—",
         "0.0000",
         n_conf >= 0.70,
         None),

        ("DeBERTa-v2 NLI",
         "Classification Accuracy (20 pairs)",
         n_acc,  None, "Descriptive",
         "91.1% (MNLI, He et al. 2021)",
         "0.00%",
         None,
         None),
    ]

    for (comp, metric, smoke_v, thresh, dir_lbl,
         full_v, fmt, smoke_pass, full_pass) in rows_data:

        def _set(col, val, bold=False, bg=None, num_fmt=None):
            c = ws.cell(row=row, column=col, value=val)
            c.font = Font(bold=bold, size=10)
            c.alignment = _center()
            c.border = _thin_border()
            if bg:
                c.fill = PatternFill("solid", fgColor=bg)
            if num_fmt:
                c.number_format = num_fmt

        _set(1, comp,   bold=True)
        _set(2, metric)
        if smoke_v is not None:
            _set(3, smoke_v, num_fmt=fmt)
        else:
            _set(3, "N/A (full set only)")
        if thresh is not None:
            _set(4, thresh, num_fmt=fmt)
        else:
            _set(4, "—")
        _set(5, dir_lbl)
        if isinstance(full_v, float):
            _set(6, full_v, num_fmt=fmt)
        else:
            _set(6, full_v)

        # Status cell: prefer full_pass; fall back to smoke_pass
        if full_pass is not None:
            status = "✓ PASS" if full_pass else "✗ FAIL"
            bg     = PASS_GREEN if full_pass else FAIL_RED
        elif smoke_pass is not None:
            status = "✓ PASS" if smoke_pass else "✗ FAIL"
            bg     = PASS_GREEN if smoke_pass else FAIL_RED
        else:
            status, bg = "—", "F2F2F2"
        _set(7, status, bold=True, bg=bg)

        ws.row_dimensions[row].height = 20
        row += 1

    row += 1
    ws.merge_cells(f"A{row}:G{row}")
    all_pass = all([
        rer_metrics["top1_accuracy_on_test_set"] >= 0.85,
        clf_metrics["test_f1_weighted"]           >= 0.95,
        clf_metrics["unseen_pair_accuracy"]        >= 0.70,
        n_conf >= 0.70,
    ])
    c = ws.cell(row=row, column=1,
                value=f"OVERALL: {'✓  ALL THRESHOLD CHECKS PASSED' if all_pass else '✗  ONE OR MORE CHECKS FAILED'}")
    c.font  = Font(bold=True, size=13, color="FFFFFF")
    c.fill  = PatternFill("solid", fgColor=(DARK_GREEN if all_pass else DARK_RED))
    c.alignment = _center()
    ws.row_dimensions[row].height = 30

    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 14
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 28
    ws.column_dimensions["G"].width = 16

# ── Sheet 2: T5 Reranker ──────────────────────────────────────────────────────

def _write_reranker(wb, results, metrics):
    ws = wb.create_sheet("T5 Reranker")
    N = 8

    # Title
    ws.merge_cells(f"A1:H1")
    c = ws["A1"]
    c.value = "Component Evaluation — T5-small Spelling Reranker"
    c.font  = Font(bold=True, size=14, color="FFFFFF")
    c.fill  = PatternFill("solid", fgColor=DARK_NAVY)
    c.alignment = _center()
    ws.row_dimensions[1].height = 28

    row = 2
    for label, val in [
        ("Base model",           "google/t5-small"),
        ("Training data",        f"Birkbeck Corpus + TOEFL-Spell (ETS) — {metrics['number_of_training_samples']:,} training pairs"),
        ("Candidate generator",  "SymSpell (Garbe 2018) — up to 5 candidates, shuffled to prevent position bias"),
        ("Full test-set size",   f"{metrics['number_of_test_samples']:,} held-out samples"),
        ("Full test Top-1 Acc.", f"{metrics['top1_accuracy_on_test_set']:.4f} ({metrics['top1_accuracy_on_test_set']*100:.2f}%)"),
        ("Smoke-test sample",    f"{len(results)} samples drawn at random (seed={RANDOM_SEED})"),
        ("Threshold",            "Top-1 Accuracy ≥ 0.85  (85%)"),
        ("Baseline (no model)",  "SymSpell candidates[0] frequency-ranked: ~72–75% Top-1 Acc. (Flor et al.)"),
        ("Threshold rationale",  "≥85% represents a ~10–13 pp improvement over the no-reranking baseline"),
    ]:
        _info_row(ws, row, label, val, n_cols=8)
        row += 1

    row += 1  # blank row
    HDR_ROW = row
    _apply_header(ws, row,
                  ["#", "Misspelled Word", "Correct Word",
                   "Candidates Shown to Model (shuffled)",
                   "Model Output", "Correct in Candidates?",
                   "PASS / FAIL", "Notes"])
    row += 1

    DATA_START = row
    for idx, r in enumerate(results, 1):
        bg = PASS_GREEN if r["match"] == "PASS" else FAIL_RED

        def _d(col, val, bold=False, num_fmt=None, align=None):
            c = ws.cell(row=row, column=col, value=val)
            c.font      = Font(bold=bold, size=10)
            c.alignment = align or _center()
            c.border    = _thin_border()
            if num_fmt:
                c.number_format = num_fmt
            if col == 7:
                c.fill = PatternFill("solid", fgColor=bg)

        _d(1, idx)
        _d(2, r["misspelled"])
        _d(3, r["correct"])
        _d(4, r["candidates"], align=_left_wrap())
        _d(5, r["predicted"])
        _d(6, r["in_cands"])
        _d(7, r["match"], bold=True)
        note = ("Correct word absent from candidate list — "
                "model cannot recover regardless of reranking"
                if r["in_cands"] == "NO" else "")
        _d(8, note, align=_left_wrap())

        if idx % 2 == 0:
            for col in range(1, 9):
                if col != 7:
                    ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=ROW_ALT)

        row += 1
    DATA_END = row - 1
    row += 1

    # Computation section
    row = _section_title(ws, row, "SMOKE-TEST METRIC COMPUTATION", N)

    PF_RANGE = f"G{DATA_START}:G{DATA_END}"
    N_ROWS   = DATA_END - DATA_START + 1

    for label, val, fmt, is_status in [
        ("Total samples in smoke test",             N_ROWS,                                  None,    False),
        ("Correct predictions (PASS)",              f'=COUNTIF({PF_RANGE},"PASS")',          None,    False),
        ("Incorrect predictions (FAIL)",            f'=COUNTIF({PF_RANGE},"FAIL")',          None,    False),
        ("Top-1 Accuracy (smoke test)",
         f'=COUNTIF({PF_RANGE},"PASS")/{N_ROWS}',                                           "0.00%", False),
        ("Threshold (≥)",                           0.85,                                    "0.00%", False),
        ("Smoke-test status",
         f'=IF(COUNTIF({PF_RANGE},"PASS")/{N_ROWS}>=0.85,"✓ PASS","✗ FAIL")',              None,    True),
        ("", "", None, False),
        ("Full test-set Top-1 Accuracy (pre-computed)",
         metrics["top1_accuracy_on_test_set"],                                               "0.00%", False),
        ("Full test-set n",                         metrics["number_of_test_samples"],       None,    False),
        ("Full test-set status",
         f'=IF({metrics["top1_accuracy_on_test_set"]}>=0.85,"✓ PASS","✗ FAIL")',           None,    True),
    ]:
        _summary_row(ws, row, label, val, fmt=fmt, is_status=is_status, n_cols=N)
        row += 1

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 48
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 22
    ws.column_dimensions["G"].width = 14
    ws.column_dimensions["H"].width = 42
    ws.freeze_panes = f"A{HDR_ROW+1}"

# ── Sheet 3: RF Error Classifier ──────────────────────────────────────────────

def _write_classifier(wb, results, metrics):
    ws = wb.create_sheet("RF Error Classifier")
    N = 9
    CLASSES = ["phonetic_sub", "reversal", "omission", "insertion", "transposition"]

    ws.merge_cells(f"A1:I1")
    c = ws["A1"]
    c.value = "Component Evaluation — RandomForest Error Type Classifier"
    c.font  = Font(bold=True, size=14, color="FFFFFF")
    c.fill  = PatternFill("solid", fgColor=DARK_NAVY)
    c.alignment = _center()
    ws.row_dimensions[1].height = 28

    row = 2
    for label, val in [
        ("Model architecture",      "RandomForest (scikit-learn)"),
        ("Training data",           f"Birkbeck Spelling Error Corpus (Mitton, 1985)"
                                    f" — {metrics['training_samples_after_balancing']:,} samples after SMOTE balancing"),
        ("Label annotation",        "Rule-based programmatic labels from dyslexia literature "
                                    "(Miles 1993, Snowling 2000, Shaywitz 2003)"),
        ("Error type classes",      " | ".join(CLASSES)),
        ("Number of features",      f"{metrics['number_of_features']} hand-engineered phonetic, "
                                    "positional, and edit-distance features"),
        ("Leakage prevention",      metrics["data_leakage_prevention_method"]),
        ("Full test set (unique pairs)",
                                    f"{metrics['test_samples_unique_pairs_only']:,} samples"),
        ("Full weighted F1",        f"{metrics['test_f1_weighted']:.4f} ({metrics['test_f1_weighted']*100:.2f}%)"),
        ("Full unseen pair accuracy",
                                    f"{metrics['unseen_pair_accuracy']:.4f} ({metrics['unseen_pair_accuracy']*100:.2f}%)"),
        ("Smoke-test sample",       f"{len(results)} samples drawn at random (seed={RANDOM_SEED})"),
        ("Threshold — Weighted F1 (≥)", "0.95  (95%)"),
        ("Threshold — Unseen Pair Acc. (≥)", "0.70  (70%)"),
        ("Majority-class baseline", "~0.60–0.65 weighted F1 on pre-SMOTE imbalanced dataset"),
        ("Threshold rationale",     "≥0.95 WF1 represents ~30 pp above trivial baseline, "
                                    "consistent with advantage of engineered features on a closed label space"),
    ]:
        _info_row(ws, row, label, val, n_cols=9)
        row += 1

    row += 1
    HDR_ROW = row
    _apply_header(ws, row,
                  ["#", "Sample ID", "Misspelled", "Correct Word",
                   "True Error Type", "Predicted Error Type",
                   "Confidence", "PASS / FAIL", "Notes"])
    row += 1

    DATA_START = row
    for idx, r in enumerate(results, 1):
        bg = PASS_GREEN if r["match"] == "PASS" else FAIL_RED

        def _d(col, val, bold=False, num_fmt=None, align=None):
            c = ws.cell(row=row, column=col, value=val)
            c.font      = Font(bold=bold, size=10)
            c.alignment = align or _center()
            c.border    = _thin_border()
            if num_fmt:
                c.number_format = num_fmt
            if col == 8:
                c.fill = PatternFill("solid", fgColor=bg)

        _d(1, idx)
        _d(2, r["sample_id"])
        _d(3, r["misspelled"])
        _d(4, r["correct"])
        _d(5, r["true_type"])
        _d(6, r["predicted"])
        _d(7, r["confidence"], num_fmt="0.00%")
        _d(8, r["match"], bold=True)
        _d(9, "", align=_left_wrap())

        if idx % 2 == 0:
            for col in range(1, 10):
                if col != 8:
                    ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=ROW_ALT)
        row += 1

    DATA_END = row - 1
    row += 1

    # ── Per-class F1 computation table ────────────────────────────────────────
    row = _section_title(ws, row, "PER-CLASS ANALYSIS — WEIGHTED F1 COMPUTATION", N)

    _apply_header(ws, row,
                  ["Error Type", "TP", "FP", "FN",
                   "Precision", "Recall", "F1 Score", "Support (n)", "Weight"],
                  bg=DARK_GREEN)
    row += 1

    TRUE_COL = "E"   # col 5 = True Error Type in data rows
    PRED_COL = "F"   # col 6 = Predicted Error Type in data rows
    N_SMOKE  = len(results)

    class_f1_refs  = []   # (F1 cell ref, Weight cell ref) for weighted sum formula
    for cls in CLASSES:
        tp_f = (f'=COUNTIFS({TRUE_COL}{DATA_START}:{TRUE_COL}{DATA_END},"{cls}",'
                f'{PRED_COL}{DATA_START}:{PRED_COL}{DATA_END},"{cls}")')
        fp_f = (f'=COUNTIF({PRED_COL}{DATA_START}:{PRED_COL}{DATA_END},"{cls}")'
                f'-COUNTIFS({TRUE_COL}{DATA_START}:{TRUE_COL}{DATA_END},"{cls}",'
                f'{PRED_COL}{DATA_START}:{PRED_COL}{DATA_END},"{cls}")')
        fn_f = (f'=COUNTIF({TRUE_COL}{DATA_START}:{TRUE_COL}{DATA_END},"{cls}")'
                f'-COUNTIFS({TRUE_COL}{DATA_START}:{TRUE_COL}{DATA_END},"{cls}",'
                f'{PRED_COL}{DATA_START}:{PRED_COL}{DATA_END},"{cls}")')

        tp_ref, fp_ref, fn_ref = f"B{row}", f"C{row}", f"D{row}"
        pre_ref, rec_ref       = f"E{row}", f"F{row}"

        pre_f = f"=IF({tp_ref}+{fp_ref}=0,0,{tp_ref}/({tp_ref}+{fp_ref}))"
        rec_f = f"=IF({tp_ref}+{fn_ref}=0,0,{tp_ref}/({tp_ref}+{fn_ref}))"
        f1_f  = f"=IF({pre_ref}+{rec_ref}=0,0,2*{pre_ref}*{rec_ref}/({pre_ref}+{rec_ref}))"
        sup_f = f'=COUNTIF({TRUE_COL}{DATA_START}:{TRUE_COL}{DATA_END},"{cls}")'
        wgt_f = f"=H{row}/{N_SMOKE}"

        vals = [cls, tp_f, fp_f, fn_f, pre_f, rec_f, f1_f, sup_f, wgt_f]
        fmts = [None, None, None, None, "0.0000", "0.0000", "0.0000", None, "0.0000"]
        for col, (val, fmt) in enumerate(zip(vals, fmts), 1):
            c = ws.cell(row=row, column=col, value=val)
            c.font      = Font(size=10)
            c.alignment = _center()
            c.border    = _thin_border()
            if fmt:
                c.number_format = fmt

        class_f1_refs.append((f"G{row}", f"I{row}"))
        row += 1

    # Weighted F1 total row
    wf1_formula = "=" + "+".join(f"({fr}*{wr})" for fr, wr in class_f1_refs)
    ws.cell(row=row, column=1, value="WEIGHTED F1 (smoke test)").font = Font(bold=True, size=10)
    ws.cell(row=row, column=1).fill      = PatternFill("solid", fgColor=SUBHDR_GRAY)
    ws.cell(row=row, column=1).alignment = _center()
    ws.cell(row=row, column=1).border    = _thin_border()
    c = ws.cell(row=row, column=2, value=wf1_formula)
    c.font           = Font(bold=True, size=10)
    c.number_format  = "0.0000"
    c.alignment      = _center()
    c.border         = _thin_border()
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=9)
    WF1_ROW = row
    row += 2

    # ── Summary ───────────────────────────────────────────────────────────────
    row = _section_title(ws, row, "SMOKE-TEST METRIC COMPUTATION", N)
    PF_RANGE = f"H{DATA_START}:H{DATA_END}"

    for label, val, fmt, is_status in [
        ("Total samples in smoke test",   N_SMOKE,                                    None,    False),
        ("Correct predictions (PASS)",   f'=COUNTIF({PF_RANGE},"PASS")',              None,    False),
        ("Weighted F1 (smoke test)",     f"=B{WF1_ROW}",                              "0.0000",False),
        ("Threshold — Weighted F1 (≥)",  0.95,                                        "0.0000",False),
        ("Weighted F1 status",
         f'=IF(B{WF1_ROW}>=0.95,"✓ PASS","✗ FAIL")',                                 None,    True),
        ("", "", None, False),
        ("Full test-set Weighted F1",    metrics["test_f1_weighted"],                 "0.0000",False),
        ("Full test-set WF1 status",
         f'=IF({metrics["test_f1_weighted"]}>=0.95,"✓ PASS","✗ FAIL")',               None,    True),
        ("Full test-set Unseen Pair Acc.",metrics["unseen_pair_accuracy"],            "0.0000",False),
        ("Unseen Pair Acc. threshold (≥)",0.70,                                       "0.0000",False),
        ("Unseen Pair Acc. status",
         f'=IF({metrics["unseen_pair_accuracy"]}>=0.70,"✓ PASS","✗ FAIL")',           None,    True),
    ]:
        _summary_row(ws, row, label, val, fmt=fmt, is_status=is_status, n_cols=N)
        row += 1

    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 18
    ws.column_dimensions["G"].width = 12
    ws.column_dimensions["H"].width = 12
    ws.column_dimensions["I"].width = 12
    ws.freeze_panes = f"A{HDR_ROW+1}"

# ── Sheet 4: DeBERTa NLI Aligner ─────────────────────────────────────────────

def _write_nli(wb, results):
    ws = wb.create_sheet("DeBERTa NLI")
    N = 8

    ws.merge_cells("A1:H1")
    c = ws["A1"]
    c.value = "Component Evaluation — DeBERTa-v2 NLI Contextual Aligner"
    c.font  = Font(bold=True, size=14, color="FFFFFF")
    c.fill  = PatternFill("solid", fgColor=DARK_NAVY)
    c.alignment = _center()
    ws.row_dimensions[1].height = 28

    row = 2
    for label, val in [
        ("Model architecture",  "DebertaV2ForSequenceClassification (microsoft/deberta-v2-xsmall, 6-layer)"),
        ("NLI classes (4)",     "entailment | contradiction | neutral | off_topic"),
        ("Smoke-test design",   "20 hand-selected sentence pairs: 10 entailment + 10 contradiction "
                                "(semantically unambiguous, for calibration verification)"),
        ("Published benchmark", "DeBERTa-v2 on MNLI: 91.1% accuracy (He et al., 2021)"),
        ("Evaluation approach", "Results reported descriptively against published MNLI benchmark; "
                                "no independent threshold for macro-F1 (would be circular or arbitrary)"),
        ("Confidence threshold","Mean softmax probability of predicted class ≥ 0.70 on 20 clear-cut pairs"),
        ("Threshold rationale", "Transformer calibration literature: well-calibrated classifiers should assign "
                                "P > 0.70 to unambiguous examples; failure indicates calibration or fine-tuning failure"),
    ]:
        _info_row(ws, row, label, val, n_cols=8)
        row += 1

    row += 1
    HDR_ROW = row
    _apply_header(ws, row,
                  ["Pair ID", "Expected Class",
                   "Premise (Context)", "Hypothesis (Corrected Sentence)",
                   "Predicted Class", "Confidence",
                   "Correct?", "All Class Scores"])
    row += 1

    DATA_START = row
    ENT_START  = row
    for idx, r in enumerate(results, 1):
        bg = PASS_GREEN if r["match"] == "PASS" else FAIL_RED

        def _d(col, val, bold=False, num_fmt=None, align=None):
            c = ws.cell(row=row, column=col, value=val)
            c.font      = Font(bold=bold, size=10)
            c.alignment = align or _center()
            c.border    = _thin_border()
            if num_fmt:
                c.number_format = num_fmt
            if col == 7:
                c.fill = PatternFill("solid", fgColor=bg)

        _d(1, r["pair_id"])
        _d(2, r["expected"])
        _d(3, r["premise"],    align=_left_wrap())
        _d(4, r["hypothesis"], align=_left_wrap())
        _d(5, r["predicted"])
        _d(6, r["confidence"], num_fmt="0.00%")
        _d(7, r["match"], bold=True)
        scores_str = "  ".join(f"{k}: {v:.3f}" for k, v in r["scores"].items())
        _d(8, scores_str, align=_left_wrap())

        if idx % 2 == 0:
            for col in range(1, 9):
                if col != 7:
                    ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=ROW_ALT)
        ws.row_dimensions[row].height = 52
        row += 1

    DATA_END  = row - 1
    ENT_END   = DATA_START + 9   # rows 1-10 are entailment
    CON_START = DATA_START + 10  # rows 11-20 are contradiction
    CON_END   = DATA_END
    row += 1

    # ── Confidence & accuracy computation ─────────────────────────────────────
    row = _section_title(ws, row, "CONFIDENCE & ACCURACY COMPUTATION", N)

    CONF_RANGE  = f"F{DATA_START}:F{DATA_END}"
    CONF_ENT    = f"F{ENT_START}:F{ENT_END}"
    CONF_CON    = f"F{CON_START}:F{CON_END}"
    PF_RANGE    = f"G{DATA_START}:G{DATA_END}"
    TOTAL_PAIRS = DATA_END - DATA_START + 1

    for label, val, fmt, is_status in [
        ("Total hand-selected pairs",           TOTAL_PAIRS,                                        None,    False),
        ("Correctly classified",               f'=COUNTIF({PF_RANGE},"PASS")',                      None,    False),
        ("Classification accuracy (20 pairs)", f'=COUNTIF({PF_RANGE},"PASS")/{TOTAL_PAIRS}',       "0.00%", False),
        ("Mean confidence — all 20 pairs",     f"=AVERAGE({CONF_RANGE})",                           "0.00%", False),
        ("Mean confidence — 10 entailment",    f"=AVERAGE({CONF_ENT})",                             "0.00%", False),
        ("Mean confidence — 10 contradiction", f"=AVERAGE({CONF_CON})",                             "0.00%", False),
        ("Confidence threshold (≥)",            0.70,                                               "0.00%", False),
        ("Confidence status",
         f'=IF(AVERAGE({CONF_RANGE})>=0.70,"✓ PASS","✗ FAIL")',                                    None,    True),
        ("", "", None, False),
        ("MNLI benchmark (He et al., 2021)",    "91.1% accuracy — DeBERTa-v2 on MNLI test set",   None,    False),
        ("Note on macro-F1",
         "Macro-F1 reported descriptively; no threshold set to avoid circular "
         "replication of the published benchmark or an arbitrary floor",                            None,    False),
    ]:
        _summary_row(ws, row, label, val, fmt=fmt, is_status=is_status, n_cols=N)
        row += 1

    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 52
    ws.column_dimensions["D"].width = 52
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 12
    ws.column_dimensions["H"].width = 46
    ws.freeze_panes = f"A{HDR_ROW+1}"

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    SEP = "=" * 70
    print(f"\n{SEP}")
    print("SALITAyo Writing Assistant - Model Evaluation Smoke Test")
    print(SEP)

    # Load stored full-evaluation metrics
    with open(os.path.join(MODELS_DIR, "reranker",
                           "final_model", "evaluation_metrics.json")) as f:
        rer_metrics = json.load(f)
    with open(os.path.join(MODELS_DIR, "error_classifier",
                           "training_metadata.json")) as f:
        clf_metrics = json.load(f)

    print("\n[1/3] T5-small Reranker")
    rer_results = _run_reranker(_load_reranker_samples(RERANKER_N))

    print("\n[2/3] RF Error Classifier")
    clf_results = _run_classifier(_load_classifier_samples(CLASSIFIER_N))

    print("\n[3/3] DeBERTa-v2 NLI Aligner")
    nli_results = _run_nli()

    print("\nBuilding Excel workbook ...")
    wb = openpyxl.Workbook()
    for s in wb.sheetnames:
        del wb[s]

    _write_summary(wb, rer_results, clf_results, nli_results, rer_metrics, clf_metrics)
    _write_reranker(wb, rer_results, rer_metrics)
    _write_classifier(wb, clf_results, clf_metrics)
    _write_nli(wb, nli_results)

    out = os.path.join(BASE_DIR, "smoke_test_results.xlsx")
    wb.save(out)

    print(f"\nSaved: {out}")
    print(SEP + "\n")


if __name__ == "__main__":
    main()
