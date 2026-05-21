"""Evaluation metrics for text simplification and restructuring quality."""

import logging
import re
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class SimplificationEvaluator:
    """Evaluate simplification quality using readability and preservation metrics."""

    def __init__(self):
        """Initialize and download required NLTK resources."""
        try:
            import nltk
            nltk.download('punkt', quiet=True)
            nltk.download('punkt_tab', quiet=True)
        except Exception as e:
            logger.warning(f"Failed to download NLTK resources: {e}")

    @staticmethod
    def calculate_fkgl(text: str) -> float:
        """Calculate Flesch-Kincaid Grade Level."""
        metrics = SimplificationEvaluator.readability_profile(text)
        return float(metrics["fkgl"])

    @staticmethod
    def _words(text: str) -> list[str]:
        return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text or "")

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [part for part in re.split(r"[.!?]+", text or "") if part.strip()]

    @staticmethod
    def readability_profile(text: str) -> dict:
        """Calculate FRE, FKGL, GFI, ASL, and ASW with deterministic tokenization."""
        words = SimplificationEvaluator._words(text)
        sentences = SimplificationEvaluator._sentences(text)
        if not words or not sentences:
            return {
                "fre": 0.0,
                "fkgl": 0.0,
                "gfi": 0.0,
                "asl": 0.0,
                "asw": 0.0,
                "word_count": 0,
                "sentence_count": 0,
                "syllable_count": 0,
                "complex_word_count": 0,
            }

        syllable_counts = [SimplificationEvaluator._count_syllables(word) for word in words]
        syllables = sum(syllable_counts)
        word_count = len(words)
        sentence_count = len(sentences)
        asl = word_count / sentence_count
        asw = syllables / word_count
        complex_words = sum(1 for count in syllable_counts if count >= 3)
        complex_ratio = complex_words / word_count

        fre = 206.835 - (1.015 * asl) - (84.6 * asw)
        fkgl = (0.39 * asl) + (11.8 * asw) - 15.59
        gfi = 0.4 * (asl + (100 * complex_ratio))

        return {
            "fre": round(float(fre), 2),
            "fkgl": round(float(max(0.0, fkgl)), 2),
            "gfi": round(float(max(0.0, gfi)), 2),
            "asl": round(float(asl), 2),
            "asw": round(float(asw), 2),
            "word_count": word_count,
            "sentence_count": sentence_count,
            "syllable_count": syllables,
            "complex_word_count": complex_words,
        }

    @staticmethod
    def _entity_terms(text: str) -> set[str]:
        """Extract simple named-entity candidates for preservation checks."""
        terms = set(re.findall(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)*\b", text or ""))
        terms.update(re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", text or ""))
        return {term.strip() for term in terms if term.strip()}

    @staticmethod
    def entity_retention_rate(original: str, simplified: str) -> dict:
        """Calculate ERR: entity retention rate from original to restructured text."""
        original_terms = SimplificationEvaluator._entity_terms(original)
        if not original_terms:
            return {
                "err": 1.0,
                "entity_count": 0,
                "preserved_entity_count": 0,
                "missing_entities": [],
            }

        simplified_lower = (simplified or "").lower()
        preserved = {
            term
            for term in original_terms
            if term.lower() in simplified_lower
        }
        missing = sorted(original_terms - preserved)

        return {
            "err": round(len(preserved) / len(original_terms), 2),
            "entity_count": len(original_terms),
            "preserved_entity_count": len(preserved),
            "missing_entities": missing,
        }

    @staticmethod
    def semantic_preservation(original: str, simplified: str) -> dict:
        """
        Calculate BERTScore F1 when available.

        If the transformer scorer cannot run in the local environment, the app
        still returns a bounded lexical similarity fallback instead of breaking
        the Reading Restructurer screen.
        """
        try:
            from bert_score import score as bert_score

            _, _, f1 = bert_score(
                [simplified or ""],
                [original or ""],
                lang="en",
                model_type="bert-base-multilingual-cased",
                verbose=False,
            )
            return {
                "bertscore_f1": round(float(f1.mean()), 4),
                "method": "bert-score",
            }
        except Exception as e:
            logger.warning("BERTScore unavailable, using lexical fallback: %s", e)
            return {
                "bertscore_f1": round(SequenceMatcher(None, original or "", simplified or "").ratio(), 4),
                "method": "lexical-fallback",
            }

    @staticmethod
    def readability_delta(original: str, simplified: str) -> dict:
        """Compare readability before and after restructuring."""
        original_profile = SimplificationEvaluator.readability_profile(original)
        simplified_profile = SimplificationEvaluator.readability_profile(simplified)
        return {
            "original": original_profile,
            "restructured": simplified_profile,
            "delta": {
                "fre": round(simplified_profile["fre"] - original_profile["fre"], 2),
                "fkgl": round(original_profile["fkgl"] - simplified_profile["fkgl"], 2),
                "gfi": round(original_profile["gfi"] - simplified_profile["gfi"], 2),
                "asl": round(original_profile["asl"] - simplified_profile["asl"], 2),
                "asw": round(original_profile["asw"] - simplified_profile["asw"], 2),
            },
        }

    @staticmethod
    def _safe_word_tokenize(text: str) -> list[str]:
        try:
            from nltk.tokenize import word_tokenize

            return word_tokenize(text or "")
        except Exception:
            return SimplificationEvaluator._words(text)

    @staticmethod
    def _safe_sentence_tokenize(text: str) -> list[str]:
        try:
            from nltk.tokenize import sent_tokenize

            return sent_tokenize(text or "")
        except Exception:
            return SimplificationEvaluator._sentences(text)

    @staticmethod
    def calculate_bleu(reference: str, hypothesis: str) -> float:
        """Calculate BLEU score (simplified version using sentence overlap)."""
        try:
            from nltk.translate.bleu_score import SmoothingFunction, sentence_bleu

            ref_tokens = SimplificationEvaluator._safe_word_tokenize(reference.lower())
            hyp_tokens = SimplificationEvaluator._safe_word_tokenize(hypothesis.lower())

            smoothing = SmoothingFunction().method1
            bleu = sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothing)
            return float(bleu)
        except Exception as e:
            logger.error(f"BLEU calculation failed: {e}")
            return 0.0

    @staticmethod
    def _count_syllables(word: str) -> int:
        """Estimate syllable count for a word."""
        word = word.lower()
        vowels = "aeiouy"
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # Adjust for silent e
        if word.endswith("e"):
            syllable_count -= 1
        
        return max(1, syllable_count)

    @staticmethod
    def calculate_sari(original: str, simplified: str, references: list[str] = None) -> dict:
        """
        Calculate SARI (Simplification Auto Rate for Individual operations).
        SARI measures: Keep, Add, Delete operations.
        """
        try:
            orig_tokens = set(SimplificationEvaluator._safe_word_tokenize(original.lower()))
            simp_tokens = set(SimplificationEvaluator._safe_word_tokenize(simplified.lower()))
            
            # Keep: words that appear in both
            kept = len(orig_tokens & simp_tokens) / len(orig_tokens) if orig_tokens else 0
            
            # Delete: words removed
            deleted = len(orig_tokens - simp_tokens) / len(orig_tokens) if orig_tokens else 0
            
            # Add: new words added (brevity penalty)
            added = 0
            if len(simp_tokens) > 0:
                new_words = simp_tokens - orig_tokens
                added = len(new_words) / len(simp_tokens)
            
            # SARI combines: keep rate, deletion rate, addition rate
            sari_score = (kept + deleted + (1 - added)) / 3
            
            return {
                "sari": float(sari_score),
                "keep_rate": float(kept),
                "delete_rate": float(deleted),
                "add_rate": float(added),
            }
        except Exception as e:
            logger.error(f"SARI calculation failed: {e}")
            return {"sari": 0.0, "keep_rate": 0.0, "delete_rate": 0.0, "add_rate": 0.0}

    @staticmethod
    def evaluate(original: str, simplified: str) -> dict:
        """Comprehensive evaluation of simplification."""
        readability = SimplificationEvaluator.readability_delta(original, simplified)
        fkgl_original = readability["original"]["fkgl"]
        fkgl_simplified = readability["restructured"]["fkgl"]
        fkgl_delta = readability["delta"]["fkgl"]

        bleu = SimplificationEvaluator.calculate_bleu(original, simplified)
        sari = SimplificationEvaluator.calculate_sari(original, simplified)
        bertscore = SimplificationEvaluator.semantic_preservation(original, simplified)
        entity_retention = SimplificationEvaluator.entity_retention_rate(original, simplified)

        return {
            "fkgl_original": float(fkgl_original),
            "fkgl_simplified": float(fkgl_simplified),
            "fkgl_delta": float(fkgl_delta),
            "fre_original": float(readability["original"]["fre"]),
            "fre_restructured": float(readability["restructured"]["fre"]),
            "fre_delta": float(readability["delta"]["fre"]),
            "gfi_original": float(readability["original"]["gfi"]),
            "gfi_restructured": float(readability["restructured"]["gfi"]),
            "gfi_delta": float(readability["delta"]["gfi"]),
            "asl_original": float(readability["original"]["asl"]),
            "asl_restructured": float(readability["restructured"]["asl"]),
            "asl_delta": float(readability["delta"]["asl"]),
            "asw_original": float(readability["original"]["asw"]),
            "asw_restructured": float(readability["restructured"]["asw"]),
            "asw_delta": float(readability["delta"]["asw"]),
            "bertscore_f1": float(bertscore["bertscore_f1"]),
            "bertscore_method": bertscore["method"],
            "err": float(entity_retention["err"]),
            "entity_count": int(entity_retention["entity_count"]),
            "preserved_entity_count": int(entity_retention["preserved_entity_count"]),
            "missing_entities": entity_retention["missing_entities"],
            "readability_profile": readability,
            "bleu": float(bleu),
            "sari": sari,
            "readability_improved": fkgl_delta > 0,
        }


def get_evaluator():
    """Factory function to get evaluator instance."""
    return SimplificationEvaluator()
