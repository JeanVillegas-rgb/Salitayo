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
        from .services.candidate_generator import _get_tight, _get_wide, load_wikipedia_misspellings
        from .services.reranker_service import _load as load_reranker
        from .services.error_classifier_service import _get_model as load_classifier
        from .services.nli_aligner_service import _load as load_nli
        from .services.retrieval_service import get_encoder

        _get_tight()
        logger.debug("[STARTUP] SymSpell tight (max_ed=2) ready.")
        _get_wide()
        logger.debug("[STARTUP] SymSpell wide (max_ed=4) ready.")

        wiki_path = os.path.join(settings.BASE_DIR, "data", "wikipedia_misspellings.txt")
        load_wikipedia_misspellings(wiki_path)
        logger.debug("[STARTUP] Wikipedia misspellings lookup ready.")

        load_reranker()
        logger.debug("[STARTUP] T5 reranker ready.")

        load_classifier()
        logger.debug("[STARTUP] RandomForest classifier ready.")

        load_nli()
        logger.debug("[STARTUP] DeBERTa NLI aligner ready.")

        get_encoder()
        logger.debug("[STARTUP] Sentence encoder (MiniLM) ready.")

        logger.debug("[STARTUP] All models loaded.")
