"""
Computes the 17 features used by the RandomForest error classifier.
Feature order must match training_metadata.json exactly.
"""
import jellyfish
import editdistance

_VOWELS = set('aeiouAEIOU')


def _ngram_overlap_ratio(a: str, b: str, n: int) -> float:
    def ngrams(s):
        return set(s[i:i + n] for i in range(len(s) - n + 1))
    sa, sb = ngrams(a.lower()), ngrams(b.lower())
    union = sa | sb
    if not union:
        return 1.0 if not sa and not sb else 0.0
    return len(sa & sb) / len(union)


def _positional_match_ratio(misspelled: str, correct: str) -> float:
    max_len = max(len(misspelled), len(correct))
    if max_len == 0:
        return 1.0
    matches = sum(
        misspelled[i] == correct[i]
        for i in range(min(len(misspelled), len(correct)))
    )
    return matches / max_len


def _shared_char_set_ratio(misspelled: str, correct: str) -> float:
    sa, sb = set(misspelled.lower()), set(correct.lower())
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def _vowel_ratio(word: str) -> float:
    if not word:
        return 0.0
    return sum(c in _VOWELS for c in word) / len(word)


def extract_features(misspelled: str, correct: str) -> list:
    """Return a list of 17 floats in the order expected by the classifier."""
    ed = editdistance.eval(misspelled, correct)
    max_len = max(len(misspelled), len(correct), 1)

    raw_edit_distance = float(ed)
    normalized_edit_distance = ed / max_len
    length_difference_signed = float(len(misspelled) - len(correct))
    absolute_length_difference = float(abs(len(correct) - len(misspelled)))

    try:
        soundex_equal = float(
            jellyfish.soundex(misspelled) == jellyfish.soundex(correct)
        )
    except Exception:
        soundex_equal = 0.0

    try:
        metaphone_equal = float(
            jellyfish.metaphone(misspelled) == jellyfish.metaphone(correct)
        )
    except Exception:
        metaphone_equal = 0.0

    jaro_winkler = jellyfish.jaro_winkler_similarity(misspelled, correct)

    bigram_overlap = _ngram_overlap_ratio(misspelled, correct, 2)
    trigram_overlap = _ngram_overlap_ratio(misspelled, correct, 3)
    positional_match = _positional_match_ratio(misspelled, correct)
    shared_char_set = _shared_char_set_ratio(misspelled, correct)

    mis_vowel_ratio = _vowel_ratio(misspelled)
    cor_vowel_ratio = _vowel_ratio(correct)
    vowel_ratio_diff = cor_vowel_ratio - mis_vowel_ratio

    correct_set = set(correct)
    misspelled_set = set(misspelled)

    misspelled_chars_not_in_correct_ratio = len(
        [char for char in misspelled if char not in correct_set]
    ) / max(len(misspelled), 1)

    correct_chars_not_in_misspelled_ratio = len(
        [char for char in correct if char not in misspelled_set]
    ) / max(len(correct), 1)

    edit_distance_to_length_diff_ratio = raw_edit_distance / max(
        abs(length_difference_signed) + 1, 1
    )

    return [
        raw_edit_distance,
        normalized_edit_distance,
        length_difference_signed,
        absolute_length_difference,
        soundex_equal,
        metaphone_equal,
        jaro_winkler,
        bigram_overlap,
        trigram_overlap,
        positional_match,
        shared_char_set,
        mis_vowel_ratio,
        cor_vowel_ratio,
        vowel_ratio_diff,
        misspelled_chars_not_in_correct_ratio,
        correct_chars_not_in_misspelled_ratio,
        edit_distance_to_length_diff_ratio,
    ]
