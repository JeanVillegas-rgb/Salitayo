"""BERT NER for identifying academic and scientific terms."""

import logging
import re

logger = logging.getLogger(__name__)


class BertNERProtector:
    """Uses BERT-based NER to identify and protect academic terms."""

    def __init__(self, model_name: str = "dslim/bert-base-NER"):
        """Initialize BERT NER model."""
        self.model_name = model_name
        self.pipeline = None
        self._initialized = False

    def _initialize_model(self):
        """Lazy load the NER pipeline (only on first use)."""
        if self._initialized:
            return
        
        try:
            from transformers import pipeline
            self.pipeline = pipeline("ner", model=self.model_name, aggregation_strategy="simple")
            logger.info(f"BERT NER model loaded: {self.model_name}")
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to load BERT NER model: {e}")
            self.pipeline = None
            self._initialized = True

    def _heuristic_entities(self, text: str) -> list[dict]:
        entities = []
        seen = set()
        
        # We only protect Acronyms and Proper Names (Upper Case)
        patterns = [
            r"\b[A-Z]{2,}[A-Z0-9\-]*\b",                      # Acronyms (WHO, NASA)
            r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b",          # Multi-word names (Albert Einstein)
            r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)+\b",              # Hyphenated names
            r"\b[A-Z][a-z]{2,}\b",                            # Single capitalized names (Manila, Jose)
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                word = match.group(0).strip()
                
                # Special Rule: don't protect single capitalized words that only look
                # important because they start a sentence.
                prefix = text[: match.start()].rstrip()
                starts_sentence = not prefix or prefix.endswith((".", "!", "?", '"', "'"))
                if starts_sentence and re.fullmatch(r"[A-Z][a-z]+", word):
                    continue

                if not word or word in seen:
                    continue
                seen.add(word)
                entities.append({"word": word, "entity_group": "MISC"})
        return entities

    def extract_entities(self, text: str) -> list[dict]:
        """Extract named entities (academic terms, proper nouns, etc.)."""
        self._initialize_model()  # Lazy load on first use
        
        # Merge BERT entities with heuristic entities for maximum coverage
        heuristic_entities = self._heuristic_entities(text)
        
        if not self.pipeline:
            return heuristic_entities

        try:
            bert_entities = self.pipeline(text)
            # Combine and deduplicate
            seen_words = {e["word"].lower() for e in bert_entities}
            for e in heuristic_entities:
                if e["word"].lower() not in seen_words:
                    bert_entities.append(e)
            return bert_entities
        except Exception as e:
            logger.error(f"NER extraction failed: {e}")
            return heuristic_entities

    def get_protected_terms(self, text: str) -> list[str]:
        """Extract entity terms that should be protected from simplification."""
        entities = self.extract_entities(text)
        protected = []
        seen = set()

        # Common words to exclude from protection even if they are capitalized
        common_exclude = {
            "this", "that", "there", "those", "these", "would", "could", "should", 
            "their", "about", "which", "the", "and", "but", "for", "with", "from",
            "they", "she", "his", "her", "your", "our", "its", "when", "where", "while"
        }

        for entity in entities:
            word = entity.get("word", "").strip()
            entity_type = entity.get("entity_group", "")
            
            word_key = word.lower()
            if (
                not word
                or word_key in common_exclude
                or word_key in seen
                or any(word_key in existing.lower().split() for existing in protected)
            ):
                continue

            # Protect People, Locations, and Organizations from BERT
            if entity_type in ["PER", "LOC", "ORG"]:
                protected.append(word)
                seen.add(word_key)
                continue

            # Protect 'MISC' terms from heuristics if they are capitalized (Names/Places)
            if entity_type == "MISC" and word[0].isupper():
                protected.append(word)
                seen.add(word_key)
                continue

            # Protect Acronyms (WHO, NASA, DNA)
            if re.fullmatch(r"[A-Z]{2,}[A-Z0-9\-]*", word):
                protected.append(word)
                seen.add(word_key)
                continue

        return list(protected)


def get_ner_protector():
    """Factory function to get NER protector instance."""
    return BertNERProtector()
