"""
Canonical Word Proficiency seed lists (English + Filipino).
Used by management command seed_words and POS sync overrides.
"""

# Three words per POS tag; rr_augmentation_level cycles 0 → 1 → 2 per group.
SEED_VOCABULARY = {
    "en": {
        "NOUN": [
            {"word": "mountain", "rr_augmentation_level": 0},
            {"word": "library", "rr_augmentation_level": 1},
            {"word": "thunder", "rr_augmentation_level": 2},
        ],
        "VERB": [
            {"word": "whisper", "rr_augmentation_level": 0},
            {"word": "gather", "rr_augmentation_level": 1},
            {"word": "stumble", "rr_augmentation_level": 2},
        ],
        "ADJ": [
            {"word": "brilliant", "rr_augmentation_level": 0},
            {"word": "fragile", "rr_augmentation_level": 1},
            {"word": "ancient", "rr_augmentation_level": 2},
        ],
        "ADV": [
            {"word": "swiftly", "rr_augmentation_level": 0},
            {"word": "barely", "rr_augmentation_level": 1},
            {"word": "gently", "rr_augmentation_level": 2},
        ],
        "PRON": [
            {"word": "himself", "rr_augmentation_level": 0},
            {"word": "herself", "rr_augmentation_level": 1},
            {"word": "themselves", "rr_augmentation_level": 2},
        ],
        "DET": [
            {"word": "every", "rr_augmentation_level": 0},
            {"word": "several", "rr_augmentation_level": 1},
            {"word": "each", "rr_augmentation_level": 2},
        ],
        "ADP": [
            {"word": "beneath", "rr_augmentation_level": 0},
            {"word": "beyond", "rr_augmentation_level": 1},
            {"word": "through", "rr_augmentation_level": 2},
        ],
        "CONJ": [
            {"word": "although", "rr_augmentation_level": 0},
            {"word": "unless", "rr_augmentation_level": 1},
            {"word": "because", "rr_augmentation_level": 2},
        ],
        "NUM": [
            {"word": "dozen", "rr_augmentation_level": 0},
            {"word": "hundred", "rr_augmentation_level": 1},
            {"word": "thousand", "rr_augmentation_level": 2},
        ],
        "OTHER": [
            {"word": "hello", "rr_augmentation_level": 0},
            {"word": "please", "rr_augmentation_level": 1},
            {"word": "maybe", "rr_augmentation_level": 2},
        ],
    },
    "fil": {
        "NOUN": [
            {"word": "bahay", "rr_augmentation_level": 0},
            {"word": "aralin", "rr_augmentation_level": 1},
            {"word": "ulan", "rr_augmentation_level": 2},
        ],
        "VERB": [
            {"word": "bumasa", "rr_augmentation_level": 0},
            {"word": "sumayaw", "rr_augmentation_level": 1},
            {"word": "tumakbo", "rr_augmentation_level": 2},
        ],
        "ADJ": [
            {"word": "maganda", "rr_augmentation_level": 0},
            {"word": "maliit", "rr_augmentation_level": 1},
            {"word": "matanda", "rr_augmentation_level": 2},
        ],
        "ADV": [
            {"word": "mabilis", "rr_augmentation_level": 0},
            {"word": "dahan-dahan", "rr_augmentation_level": 1},
            {"word": "palagi", "rr_augmentation_level": 2},
        ],
        "PRON": [
            {"word": "ako", "rr_augmentation_level": 0},
            {"word": "ikaw", "rr_augmentation_level": 1},
            {"word": "sila", "rr_augmentation_level": 2},
        ],
        "DET": [
            {"word": "ang", "rr_augmentation_level": 0},
            {"word": "mga", "rr_augmentation_level": 1},
            {"word": "lahat", "rr_augmentation_level": 2},
        ],
        "ADP": [
            {"word": "sa", "rr_augmentation_level": 0},
            {"word": "mula", "rr_augmentation_level": 1},
            {"word": "hanggang", "rr_augmentation_level": 2},
        ],
        "CONJ": [
            {"word": "at", "rr_augmentation_level": 0},
            {"word": "pero", "rr_augmentation_level": 1},
            {"word": "dahil", "rr_augmentation_level": 2},
        ],
        "NUM": [
            {"word": "isa", "rr_augmentation_level": 0},
            {"word": "dalawa", "rr_augmentation_level": 1},
            {"word": "sampu", "rr_augmentation_level": 2},
        ],
        "OTHER": [
            {"word": "kamusta", "rr_augmentation_level": 0},
            {"word": "salamat", "rr_augmentation_level": 1},
            {"word": "oo", "rr_augmentation_level": 2},
        ],
    },
}


def build_seed_entries(locale: str) -> list[dict]:
    """Flatten vocabulary for one locale with pos_tag and language set."""
    locale = locale if locale in SEED_VOCABULARY else "en"
    entries = []
    for pos_tag, words in SEED_VOCABULARY[locale].items():
        for entry in words:
            entries.append({
                **entry,
                "word": entry["word"].strip().lower(),
                "pos_tag": pos_tag,
                "language": locale,
            })
    return entries


def get_seed_overrides() -> dict[str, dict]:
    """word → {pos_tag, language} for retag/sync."""
    overrides = {}
    for locale, by_pos in SEED_VOCABULARY.items():
        for pos_tag, words in by_pos.items():
            for entry in words:
                overrides[entry["word"].strip().lower()] = {
                    "pos_tag": pos_tag,
                    "language": locale,
                }
    return overrides


def seed_words_flat(locale: str | None = None) -> list[str]:
    """Simple word list for frontend-style fallbacks."""
    if locale and locale in SEED_VOCABULARY:
        locales = [locale]
    else:
        locales = list(SEED_VOCABULARY.keys())
    out = []
    for loc in locales:
        for words in SEED_VOCABULARY[loc].values():
            out.extend(w["word"] for w in words)
    return out
