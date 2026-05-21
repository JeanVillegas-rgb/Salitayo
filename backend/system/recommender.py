"""
recommender.py — session word selection and propagation hooks.
"""

from .models import WordState, WordFeatures, AUG_LEVEL_LABELS, MAX_AUGMENTATION_LEVEL, WordProgressionService

WEIGHT_FREQUENCY   = 3.0
WEIGHT_SEVERITY    = 2.0
WEIGHT_AUG_LEVEL   = 1.5
WEIGHT_STREAK_MISS = 1.0
BONUS_UNSEEN       = 2.0
PENALTY_MASTERED   = -4.0

MASTERY_THRESHOLD  = 0.85
MIN_RECENT_HISTORY = 5


def _score(ws: WordState) -> float:
    score = (
        ws.frequency_weight     * WEIGHT_FREQUENCY
        + ws.severity_score     * WEIGHT_SEVERITY
        + ws.augmentation_level * WEIGHT_AUG_LEVEL
        + ws.streak_miss        * WEIGHT_STREAK_MISS
    )
    if ws.total_attempts == 0:
        score += BONUS_UNSEEN
    if (
        len(ws.attempt_history) >= MIN_RECENT_HISTORY
        and (ws.recent_accuracy or 0) >= MASTERY_THRESHOLD
        and ws.augmentation_level == 0
    ):
        score += PENALTY_MASTERED
    return score


def compose_session(
    user_id: int,
    session_size: int = 10,
    pos_tag: str | None = None,
    word_ids: list | None = None,
) -> list:
    session_size = session_size or 10

    qs = (
        WordState.objects
        .filter(user_id=user_id)
        .select_related("features")
    )
    if word_ids:
        qs = qs.filter(id__in=word_ids)
    elif pos_tag:
        qs = qs.filter(features__pos_tag=pos_tag.upper())

    all_words = list(qs)
    if not all_words:
        return []

    active   = [ws for ws in all_words if not _is_mastered(ws)]
    mastered = [ws for ws in all_words if _is_mastered(ws)]
    pool = active if len(active) >= session_size else active + mastered

    if word_ids:
        id_order = {wid: idx for idx, wid in enumerate(word_ids)}
        pool.sort(key=lambda w: id_order.get(w.id, 999))
    else:
        pool.sort(key=_score, reverse=True)

    return pool[:session_size]


def _is_mastered(ws: WordState) -> bool:
    return (
        len(ws.attempt_history) >= MIN_RECENT_HISTORY
        and (ws.recent_accuracy or 0) >= MASTERY_THRESHOLD
        and ws.augmentation_level == 0
    )


def propagate_escalation(source_ws: WordState, context_words: list) -> list:
    log = []
    for cf in context_words:
        if cf.id == source_ws.id:
            continue
        try:
            sf = cf.features
        except WordFeatures.DoesNotExist:
            continue
        if sf.pos_tag != source_ws.features.pos_tag:
            continue
        if abs(sf.syllable_count - source_ws.features.syllable_count) > 1:
            continue
        if cf.augmentation_level < MAX_AUGMENTATION_LEVEL:
            cf.augmentation_level += 1
            cf.status = "escalated"
            WordProgressionService._sync_gap(cf)
            cf.save()
            log.append({"word": cf.word, "action": "pre_escalated"})
        else:
            WordProgressionService.soft_boost(cf)
            log.append({"word": cf.word, "action": "soft_boost"})
    return log


def propagate_regression(source_ws: WordState, context_words: list) -> list:
    log = []
    for cf in context_words:
        if cf.id == source_ws.id:
            continue
        try:
            if cf.features.pos_tag != source_ws.features.pos_tag:
                continue
        except WordFeatures.DoesNotExist:
            continue
        WordProgressionService.soft_boost(cf, freq_delta=0.2)
        log.append({"word": cf.word, "action": "soft_boost"})
    return log
