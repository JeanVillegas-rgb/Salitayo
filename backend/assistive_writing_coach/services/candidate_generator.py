"""
Generates spelling correction candidates using SymSpell.

Two SymSpell singleton instances are maintained:
  _sym_spell_tight  — max_edit_distance=2, used for normal lookups and is_known_word
  _sym_spell_wide   — max_edit_distance=4, used only for phonetic expansion

A Wikipedia Common Misspellings lookup is also available as a third fallback,
loaded once at startup via load_wikipedia_misspellings().

Candidate generation order:
  1. Tight SymSpell lookup (max_ed=2, Verbosity.CLOSEST)
  2. Wide SymSpell expansion (max_ed=4, Verbosity.ALL) when the tight pool is
     thin or the best tight match is already 2 edits away
  3. Wikipedia misspellings lookup — appended last so the reranker sees it but
     SymSpell's frequency-ranked candidates take priority in the pool ordering
"""
import logging
from pathlib import Path

try:
    import symspellpy
    from symspellpy import SymSpell, Verbosity
except ImportError:
    symspellpy = None
    SymSpell = None
    Verbosity = None

logger = logging.getLogger(__name__)

_DICT_PATH = (
    Path(symspellpy.__file__).parent / "frequency_dictionary_en_82_765.txt"
    if symspellpy is not None
    else None
)

_sym_spell_tight: SymSpell | None = None
_sym_spell_wide: SymSpell | None = None

# Wikipedia Common Misspellings lookup: misspelled_lower → correct_word
wikipedia_misspelling_lookup: dict[str, str] = {}


def _get_tight() -> SymSpell:
    if SymSpell is None or _DICT_PATH is None:
        raise RuntimeError("SymSpell is not installed.")
    global _sym_spell_tight
    if _sym_spell_tight is None:
        _sym_spell_tight = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        _sym_spell_tight.load_dictionary(str(_DICT_PATH), term_index=0, count_index=1)
        logger.debug("[CANDIDATES] Tight SymSpell (max_ed=2) loaded.")
    return _sym_spell_tight


def _get_wide() -> SymSpell:
    if SymSpell is None or _DICT_PATH is None:
        raise RuntimeError("SymSpell is not installed.")
    global _sym_spell_wide
    if _sym_spell_wide is None:
        _sym_spell_wide = SymSpell(max_dictionary_edit_distance=4, prefix_length=7)
        _sym_spell_wide.load_dictionary(str(_DICT_PATH), term_index=0, count_index=1)
        logger.debug("[CANDIDATES] Wide SymSpell (max_ed=4) loaded.")
    return _sym_spell_wide


def load_wikipedia_misspellings(path: str) -> None:
    """
    Parse the Wikipedia Common Misspellings file (one 'misspelling->correct' per
    line, multiple corrections separated by commas — only the first is kept) and
    populate wikipedia_misspelling_lookup.
    """
    global wikipedia_misspelling_lookup
    lookup: dict[str, str] = {}
    skipped = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or "->" not in line:
                skipped += 1
                continue
            misspelled, corrections = line.split("->", 1)
            correct = corrections.split(",")[0].strip()
            if misspelled and correct:
                lookup[misspelled.lower()] = correct.lower()
    wikipedia_misspelling_lookup = lookup
    logger.debug(
        f"[CANDIDATES] Wikipedia misspellings loaded: {len(lookup)} entries "
        f"(skipped {skipped} malformed lines)."
    )


def get_candidates(word: str, max_candidates: int = 5) -> list[str]:
    """
    Return a candidate pool for word (up to max_candidates * 2 entries).

    Pool order:
      1. Tight SymSpell candidates (closest edit distance, highest frequency first)
      2. Wide SymSpell expansion (if pool is thin or best match is at edge of tight range)
      3. Wikipedia misspelling correction (if word is in the lookup and not already present)

    The reranker makes the final selection from the full pool.
    """
    word_lower = word.lower()
    if SymSpell is None:
        wiki_suggestion = wikipedia_misspelling_lookup.get(word_lower)
        return [wiki_suggestion] if wiki_suggestion else [word_lower]

    tight = _get_tight()

    # ── 1. Tight lookup (max_edit_distance=2) ───────────────
    tight_suggestions = tight.lookup(
        word_lower, Verbosity.CLOSEST, max_edit_distance=2, include_unknown=False
    )

    seen: list[str] = []
    top_distance = 0
    for i, s in enumerate(tight_suggestions):
        if s.term not in seen:
            seen.append(s.term)
        if i == 0:
            top_distance = s.distance
        if len(seen) >= max_candidates:
            break

    logger.debug(
        f"[CANDIDATES] '{word}' tight → {seen}  "
        f"(top_dist={top_distance}, count={len(seen)})"
    )

    # ── 2. Wide expansion (max_edit_distance=4, Verbosity.ALL) ──
    needs_expansion = len(seen) < max_candidates or top_distance >= 2

    if needs_expansion:
        wide = _get_wide()
        wide_suggestions = wide.lookup(
            word_lower, Verbosity.ALL, max_edit_distance=4, include_unknown=False
        )
        added: list[str] = []
        for s in wide_suggestions:
            if s.term not in seen:
                seen.append(s.term)
                added.append(s.term)
            if len(seen) >= max_candidates * 2:
                break
        logger.debug(f"[CANDIDATES] '{word}' wide expansion → added {added}")

    # ── 3. Wikipedia misspellings fallback ───────────────────
    wiki_suggestion = wikipedia_misspelling_lookup.get(word_lower)
    if wiki_suggestion and wiki_suggestion not in seen:
        seen.append(wiki_suggestion)
        logger.debug(
            f"[CANDIDATES] '{word}' wikipedia fallback → added '{wiki_suggestion}'"
        )

    # Return the word itself only if absolutely nothing was found, so the
    # pipeline's `candidates[0] == word.lower()` guard can reject it cleanly.
    if not seen:
        return [word_lower]

    return seen


def is_known_word(word: str) -> bool:
    """Return True if SymSpell considers the word correctly spelled (edit_distance == 0)."""
    if SymSpell is None:
        return False
    suggestions = _get_tight().lookup(word.lower(), Verbosity.TOP, max_edit_distance=0)
    return bool(suggestions)
