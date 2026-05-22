import logging
from django.apps import AppConfig

logger = logging.getLogger('assistive_writing_coach')


class AssistiveWritingCoachConfig(AppConfig):
    name = 'assistive_writing_coach'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        logger.debug("[STARTUP] Pre-loading NLP models...")

        import os
        from django.conf import settings

        try:
            from .services.candidate_generator import _get_tight, _get_wide, load_wikipedia_misspellings

            _get_tight()
            logger.debug("[STARTUP] SymSpell tight (max_ed=2) ready.")
            _get_wide()
            logger.debug("[STARTUP] SymSpell wide (max_ed=4) ready.")

            wiki_path = os.path.join(settings.BASE_DIR, "data", "wikipedia_misspellings.txt")
            try:
                load_wikipedia_misspellings(wiki_path)
                logger.debug("[STARTUP] Wikipedia misspellings lookup ready.")
            except Exception as e:
                logger.warning(f"[STARTUP] Could not load Wikipedia misspellings: {e}")
        except (ImportError, RuntimeError) as e:
            logger.warning(
                "[STARTUP] SymSpell unavailable (%s). Writing Assistant spell-check is disabled.",
                e,
            )

        try:
            from .services.reranker_service import _load as load_reranker

            load_reranker()
            logger.debug("[STARTUP] T5 reranker ready.")
        except Exception as e:
            logger.warning(f"[STARTUP] Could not load T5 reranker (Writing Assistant may be degraded): {e}")

        try:
            from .services.error_classifier_service import _get_model as load_classifier

            load_classifier()
            logger.debug("[STARTUP] RandomForest classifier ready.")
        except Exception as e:
            logger.warning(f"[STARTUP] Could not load RandomForest classifier: {e}")

        try:
            from .services.nli_aligner_service import _load as load_nli

            load_nli()
            logger.debug("[STARTUP] DeBERTa NLI aligner ready.")
        except Exception as e:
            logger.warning(f"[STARTUP] Could not load DeBERTa NLI aligner: {e}")

        try:
            from .services.retrieval_service import get_encoder

            get_encoder()
            logger.debug("[STARTUP] Sentence encoder (MiniLM) ready.")
        except Exception as e:
            logger.warning(f"[STARTUP] Could not load Sentence encoder: {e}")

        logger.debug("[STARTUP] Pre-loading process complete.")
