"""Evaluation metrics for text simplification: SARI, BLEU, FKGL."""

import logging
import re

logger = logging.getLogger(__name__)


class SimplificationEvaluator:
    """Evaluate simplification quality using SARI, BLEU, and FKGL metrics."""

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
        try:
            import nltk
            from nltk.tokenize import sent_tokenize, word_tokenize
            
            sentences = sent_tokenize(text)
            words = word_tokenize(text)
            syllables = sum(SimplificationEvaluator._count_syllables(word) for word in words)
            
            if len(words) == 0 or len(sentences) == 0:
                return 0.0
            
            fkgl = (0.39 * (len(words) / len(sentences))) + (11.8 * (syllables / len(words))) - 15.59
            return max(0.0, fkgl)
        except Exception as e:
            logger.error(f"FKGL calculation failed: {e}")
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
    def calculate_bleu(reference: str, hypothesis: str) -> float:
        """Calculate BLEU score (simplified version using sentence overlap)."""
        try:
            from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
            from nltk.tokenize import word_tokenize
            
            ref_tokens = word_tokenize(reference.lower())
            hyp_tokens = word_tokenize(hypothesis.lower())
            
            smoothing = SmoothingFunction().method1
            bleu = sentence_bleu([ref_tokens], hyp_tokens, smoothing_function=smoothing)
            return float(bleu)
        except Exception as e:
            logger.error(f"BLEU calculation failed: {e}")
            return 0.0

    @staticmethod
    def calculate_sari(original: str, simplified: str, references: list[str] = None) -> dict:
        """
        Calculate SARI (Simplification Auto Rate for Individual operations).
        SARI measures: Keep, Add, Delete operations.
        """
        try:
            from nltk.tokenize import word_tokenize
            
            orig_tokens = set(word_tokenize(original.lower()))
            simp_tokens = set(word_tokenize(simplified.lower()))
            
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
        fkgl_original = SimplificationEvaluator.calculate_fkgl(original)
        fkgl_simplified = SimplificationEvaluator.calculate_fkgl(simplified)
        fkgl_delta = fkgl_original - fkgl_simplified
        
        bleu = SimplificationEvaluator.calculate_bleu(original, simplified)
        sari = SimplificationEvaluator.calculate_sari(original, simplified)
        
        return {
            "fkgl_original": float(fkgl_original),
            "fkgl_simplified": float(fkgl_simplified),
            "fkgl_delta": float(fkgl_delta),
            "bleu": float(bleu),
            "sari": sari,
            "readability_improved": fkgl_delta > 0,
        }


def get_evaluator():
    """Factory function to get evaluator instance."""
    return SimplificationEvaluator()
