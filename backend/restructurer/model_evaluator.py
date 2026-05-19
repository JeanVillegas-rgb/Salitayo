"""
Evaluation metrics for text restructuring quality.

Implements multiple metrics to assess the quality of restructured text:
- BLEU: Matches with reference text
- BERTScore: Semantic similarity
- Readability: Simplification quality
- Length metrics: Text compression
"""

import re
import logging
from typing import List, Dict, Tuple
from collections import Counter

import numpy as np
from bert_score import score as bert_score
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

logger = logging.getLogger(__name__)


class TextEvaluator:
    """Evaluate restructured text quality."""

    def __init__(self):
        """Initialize evaluator with NLTK resources."""
        try:
            stopwords.words("english")
        except:
            import nltk
            nltk.download("stopwords", quiet=True)
            nltk.download("punkt", quiet=True)

    @staticmethod
    def bleu_score(hypothesis: str, reference: str) -> float:
        """
        Calculate BLEU score between hypothesis and reference.

        Args:
            hypothesis: Generated/restructured text
            reference: Reference text

        Returns:
            BLEU score (0-1)
        """
        # Tokenize
        hyp_tokens = word_tokenize(hypothesis.lower())
        ref_tokens = word_tokenize(reference.lower())

        # Calculate unigram overlap
        hyp_counter = Counter(hyp_tokens)
        ref_counter = Counter(ref_tokens)

        overlap = sum((hyp_counter & ref_counter).values())
        bleu = overlap / max(len(hyp_tokens), 1)

        return min(bleu, 1.0)

    @staticmethod
    def bert_score_similarity(
        hypothesis: str, reference: str, lang: str = "en"
    ) -> Dict[str, float]:
        """
        Calculate BERTScore semantic similarity.

        Args:
            hypothesis: Generated/restructured text
            reference: Reference text
            lang: Language code

        Returns:
            Dict with precision, recall, f1
        """
        try:
            P, R, F1 = bert_score(
                [hypothesis], [reference], lang=lang, model_type="bert-base-multilingual-cased"
            )
            return {
                "precision": float(P.mean()),
                "recall": float(R.mean()),
                "f1": float(F1.mean()),
            }
        except Exception as e:
            logger.warning(f"BERTScore calculation failed: {e}")
            return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    @staticmethod
    def readability_metrics(text: str) -> Dict[str, float]:
        """
        Calculate readability metrics (Flesch-Kincaid, etc.).

        Args:
            text: Text to analyze

        Returns:
            Dict with readability scores
        """
        # Basic metrics
        sentences = sent_tokenize(text)
        words = word_tokenize(text.lower())
        
        # Filter out punctuation
        words = [w for w in words if w.isalnum() or "-" in w]
        
        if not sentences or not words:
            return {
                "avg_word_length": 0,
                "avg_sentence_length": 0,
                "syllable_ratio": 0,
                "readability_score": 0,
            }

        # Average word length
        avg_word_length = sum(len(w) for w in words) / len(words)

        # Average sentence length
        avg_sentence_length = len(words) / len(sentences)

        # Syllable estimation (rough: count vowels)
        syllables = 0
        for word in words:
            vowels = sum(1 for c in word.lower() if c in "aeiouy")
            syllables += max(1, vowels)

        syllable_ratio = syllables / len(words) if words else 0

        # Flesch Kincaid Grade (simplified)
        grade = (
            0.39 * avg_sentence_length
            + 11.8 * syllable_ratio
            - 15.59
        )
        grade = max(0, min(grade, 18))  # Clamp to 0-18

        return {
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "syllable_ratio": round(syllable_ratio, 2),
            "readability_grade": round(grade, 2),
        }

    @staticmethod
    def compression_ratio(original: str, restructured: str) -> float:
        """
        Calculate text compression ratio.

        Args:
            original: Original text
            restructured: Restructured text

        Returns:
            Compression ratio (restructured_length / original_length)
        """
        orig_len = len(original.split())
        restr_len = len(restructured.split())
        return restr_len / orig_len if orig_len > 0 else 1.0

    @staticmethod
    def vocabulary_simplicity(original: str, restructured: str) -> Dict[str, float]:
        """
        Compare vocabulary complexity.

        Args:
            original: Original text
            restructured: Restructured text

        Returns:
            Dict with vocabulary metrics
        """
        orig_words = set(w.lower() for w in word_tokenize(original) if w.isalnum())
        restr_words = set(w.lower() for w in word_tokenize(restructured) if w.isalnum())

        # Type-token ratio (diversity)
        if orig_words:
            orig_ttr = len(orig_words) / len(word_tokenize(original)) if word_tokenize(original) else 0
        else:
            orig_ttr = 0

        if restr_words:
            restr_ttr = len(restr_words) / len(word_tokenize(restructured)) if word_tokenize(restructured) else 0
        else:
            restr_ttr = 0

        # Vocabulary overlap
        overlap = len(orig_words & restr_words)
        overlap_ratio = overlap / len(orig_words) if orig_words else 0

        return {
            "original_unique_words": len(orig_words),
            "restructured_unique_words": len(restr_words),
            "vocabulary_preserved": round(overlap_ratio, 2),
            "original_ttr": round(orig_ttr, 2),
            "restructured_ttr": round(restr_ttr, 2),
        }

    def evaluate_pair(
        self, original: str, restructured: str, reference: str = None
    ) -> Dict:
        """
        Comprehensive evaluation of a single text pair.

        Args:
            original: Original text
            restructured: Restructured text
            reference: Optional reference restructured text

        Returns:
            Dict with all evaluation metrics
        """
        metrics = {
            "readability": self.readability_metrics(restructured),
            "compression": self.compression_ratio(original, restructured),
            "vocabulary": self.vocabulary_simplicity(original, restructured),
        }

        if reference:
            metrics["bleu"] = self.bleu_score(restructured, reference)
            metrics["bert_score"] = self.bert_score_similarity(restructured, reference)

        return metrics

    def batch_evaluate(
        self,
        originals: List[str],
        restructured: List[str],
        references: List[str] = None,
    ) -> Dict:
        """
        Evaluate multiple pairs and compute aggregate statistics.

        Args:
            originals: List of original texts
            restructured: List of restructured texts
            references: Optional list of reference texts

        Returns:
            Dict with aggregate metrics
        """
        if len(originals) != len(restructured):
            raise ValueError("Mismatch between originals and restructured texts")

        results = []
        for i in range(len(originals)):
            ref = references[i] if references else None
            result = self.evaluate_pair(originals[i], restructured[i], ref)
            results.append(result)

        # Aggregate metrics
        aggregate = {
            "num_samples": len(results),
            "avg_readability_grade": np.mean(
                [r["readability"]["readability_grade"] for r in results]
            ),
            "avg_compression": np.mean([r["compression"] for r in results]),
            "avg_vocab_preserved": np.mean(
                [r["vocabulary"]["vocabulary_preserved"] for r in results]
            ),
        }

        if references:
            aggregate["avg_bleu"] = np.mean([r.get("bleu", 0) for r in results])
            bert_f1s = [r.get("bert_score", {}).get("f1", 0) for r in results]
            aggregate["avg_bert_f1"] = np.mean(bert_f1s)

        return aggregate


# Utility function for Django management command
def evaluate_model_performance(
    model_predictions: List[str],
    gold_references: List[str],
    originals: List[str],
) -> Dict:
    """
    Evaluate model performance using all metrics.

    Useful for Django management commands or batch evaluation.

    Args:
        model_predictions: Model's restructured texts
        gold_references: Human-created references
        originals: Original texts

    Returns:
        Comprehensive evaluation results
    """
    evaluator = TextEvaluator()
    return evaluator.batch_evaluate(originals, model_predictions, gold_references)
