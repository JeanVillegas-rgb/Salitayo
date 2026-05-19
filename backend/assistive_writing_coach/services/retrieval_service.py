"""
RAG retrieval using paraphrase-MiniLM-L3-v2.
Finds the most semantically similar reference sentence for a given learner sentence.
Loaded once as a module-level singleton via AppConfig.ready().
"""
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_encoder: SentenceTransformer | None = None


def get_encoder() -> SentenceTransformer:
    global _encoder
    if _encoder is None:
        logger.debug("[RETRIEVAL] Loading paraphrase-MiniLM-L3-v2...")
        _encoder = SentenceTransformer("paraphrase-MiniLM-L3-v2")
        logger.debug("[RETRIEVAL] Encoder ready.")
    return _encoder


def retrieve_best_sentence(
    query_sentence: str, reference_sentences: list[str]
) -> tuple[str, float]:
    """
    Return (best_reference_sentence, cosine_similarity_score).
    Embeddings are L2-normalised so cosine similarity == dot product.
    """
    encoder = get_encoder()
    query_emb = encoder.encode([query_sentence], normalize_embeddings=True)
    ref_embs = encoder.encode(reference_sentences, normalize_embeddings=True)

    scores = (ref_embs @ query_emb.T).flatten()
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])

    logger.debug(
        f"[RETRIEVAL] query   : {repr(query_sentence[:80])}"
    )
    logger.debug(
        f"[RETRIEVAL] matched : {repr(reference_sentences[best_idx][:80])}  "
        f"(sim={best_score:.4f})"
    )

    return reference_sentences[best_idx], best_score
