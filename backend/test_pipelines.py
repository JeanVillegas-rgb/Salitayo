"""
Quick smoke test for both pipelines.
Run from backend/:  python test_pipelines.py
"""
import os, sys, django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salitayo.settings")
django.setup()

from assistive_writing_coach.services.pipeline import analyze
from assistive_writing_coach.services.filipino_pipeline import analyze_filipino
from assistive_writing_coach.views import _classify_input

SEP = "-" * 60

# ── ENGLISH TESTS ─────────────────────────────────────────────

ENGLISH_CASES = [
    # (label, text, expected_corrections)
    ("Classic reversal",      "She recieved the lettre.",          ["received", "letter"]),
    ("Omission",              "The begining of the storey.",       ["beginning", "story"]),
    ("Insertion",             "Thhe quik brwon fox.",              ["the",      "quick", "brown"]),
    ("Phonetic sub",          "She wuz very eksited.",             ["was",  "excited"]),
    ("Transposition",         "The wierd scohol felt emtpy.",      ["weird", "school", "empty"]),
]

print(f"\n{'='*60}")
print("ENGLISH PIPELINE TESTS")
print(f"{'='*60}")

english_pass = 0
for label, text, expected in ENGLISH_CASES:
    result = analyze(text)
    corrections = [e["correction"] for e in result["errors"]]
    words       = [e["word"]       for e in result["errors"]]
    types       = [e["error_type"] for e in result["errors"]]

    hits = sum(1 for ex in expected if ex in corrections)
    status = "PASS" if hits == len(expected) else f"PARTIAL ({hits}/{len(expected)})"
    if status == "PASS":
        english_pass += 1

    print(f"\n[{status}] {label}")
    print(f"  Input     : {text}")
    print(f"  Expected  : {expected}")
    print(f"  Got       : {corrections}")
    print(f"  Error types: {list(zip(words, types))}")

print(f"\nEnglish: {english_pass}/{len(ENGLISH_CASES)} passed")

# ── LANGUAGE DETECTION TESTS ──────────────────────────────────

DETECTION_CASES = [
    ("Pure English",   "The quick brown fox jumped over the lazy dog.", "english"),
    ("Pure Filipino",  "Ang mabilis na kayumanggi na lobo ay lumukso sa tamad na aso.", "filipino"),
    ("Taglish",        "Ang bata ay very excited para sa school ngayon.", "taglish_to_filipino"),
]

print(f"\n{'='*60}")
print("LANGUAGE DETECTION TESTS")
print(f"{'='*60}")

detect_pass = 0
for label, text, expected_lang in DETECTION_CASES:
    detected = _classify_input(text, "auto")
    ok = detected == expected_lang
    if ok:
        detect_pass += 1
    print(f"\n[{'PASS' if ok else 'FAIL'}] {label}")
    print(f"  Text     : {text[:60]}")
    print(f"  Expected : {expected_lang}  |  Got: {detected}")

print(f"\nDetection: {detect_pass}/{len(DETECTION_CASES)} passed")

# ── FILIPINO PIPELINE TESTS ───────────────────────────────────

FILIPINO_CASES = [
    ("No errors",          "Ang bata ay kumain ng kanin.",               0),
    ("Omission",           "Ang bta ay kumain ng kanin.",                1),
    ("Insertion",          "Ang baata ay kumakain ng kanin.",            1),
    ("Multiple errors",    "Ang bta ay kumaikn sa paarlan ngayon.",      3),
]

print(f"\n{'='*60}")
print("FILIPINO PIPELINE TESTS  (Groq inference)")
print(f"{'='*60}")

filipino_pass = 0
for label, text, min_errors in FILIPINO_CASES:
    try:
        result = analyze_filipino(text)
        errors = result["errors"]
        found  = len(errors)
        ok     = found >= min_errors
        if ok:
            filipino_pass += 1

        print(f"\n[{'PASS' if ok else 'FAIL'}] {label}")
        print(f"  Input      : {text}")
        print(f"  Errors     : {found}  (expected >= {min_errors})")
        for e in errors:
            print(f"    '{e['word']}' → '{e['correction']}'  [{e['error_type']} {e['error_type_confidence']*100:.0f}%]")
            print(f"    Feedback: {e['feedback']}")
        print(f"  Corrected  : {result['corrected_text']}")

    except Exception as exc:
        print(f"\n[ERROR] {label}: {exc}")

print(f"\nFilipino: {filipino_pass}/{len(FILIPINO_CASES)} passed")
print(f"\n{'='*60}")
print(f"TOTAL: English {english_pass}/{len(ENGLISH_CASES)}  |  "
      f"Detection {detect_pass}/{len(DETECTION_CASES)}  |  "
      f"Filipino {filipino_pass}/{len(FILIPINO_CASES)}")
print(f"{'='*60}\n")
