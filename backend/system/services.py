"""services.py — orchestration for word proficiency."""

from django.db import connection

from .bert_tagger import analyze_word
from .classifier import train as train_classifier
from .session_engine import WordProficiencySession
from .models import WordState, WordFeatures, MAX_AUGMENTATION_LEVEL


def language_column_ready() -> bool:
    """True when migration 0004_wordfeatures_language has been applied."""
    try:
        with connection.cursor() as cursor:
            description = connection.introspection.get_table_description(
                cursor, "system_wordfeatures"
            )
        return any(col.name == "language" for col in description)
    except Exception:
        return False


def import_word_list(user_id: int, words: list) -> dict:
    created, skipped = [], []
    for entry in _normalize_words(words):
        word = entry["word"]
        rr_level = max(0, min(MAX_AUGMENTATION_LEVEL, int(entry.get("rr_augmentation_level", 0))))
        if WordState.objects.filter(user_id=user_id, word=word).exists():
            skipped.append(word)
            continue
        analysis = _safe_analyze_word(word)
        pos_tag = entry.get("pos_tag") or analysis["pos_tag"]
        language = entry.get("language") or "en"
        if language not in ("en", "fil"):
            language = "en"
        lang_ready = language_column_ready()
        ws = WordState.objects.create(
            user_id=user_id,
            word=word,
            augmentation_level=rr_level,
            initial_augmentation_level=rr_level,
            augmentation_gap=0,
            status="pending",
        )
        WordFeatures.objects.create(
            word_state=ws,
            language=language,
            pos_tag=pos_tag,
            syllable_count=analysis["syllable_count"],
            bert_embedding=analysis.get("bert_embedding") or [0.0] * 768,
            morphological_pattern=analysis.get("morphological_pattern", ""),
            rule_features=analysis.get("rule_features", {}),
        )
        created.append({"word": word, "rr_augmentation_level": rr_level})
    return {
        "total_input": len(words),
        "created": len(created),
        "already_known": len(skipped),
        "created_words": created,
        "skipped_words": skipped,
    }


def get_session(user_id: int, groq_api_key: str, session_size: int = 10) -> WordProficiencySession:
    return WordProficiencySession(user_id, groq_api_key, int(session_size or 10))


def resume_session(user_id: int, groq_api_key: str) -> WordProficiencySession:
    return WordProficiencySession.resume(user_id, groq_api_key)


def run_training(user_id: int = None) -> dict:
    return train_classifier(user_id=user_id)


def get_seed_overrides() -> dict:
    from .seed_vocabulary import get_seed_overrides as _overrides
    return _overrides()


def sync_user_pos_tags(user_id: int) -> dict:
    return retag_user_words(user_id, seed_overrides=get_seed_overrides())


def retag_user_words(user_id: int, seed_overrides: dict | None = None) -> dict:
    raw = seed_overrides or {}
    overrides = {}
    for key, val in raw.items():
        k = key.lower()
        if isinstance(val, dict):
            overrides[k] = {
                "pos_tag": str(val.get("pos_tag", "OTHER")).upper(),
                "language": val.get("language") or "en",
            }
        else:
            overrides[k] = {"pos_tag": str(val).upper(), "language": "en"}

    updated = created = 0
    for ws in WordState.objects.filter(user_id=user_id):
        key = ws.word.lower()
        analysis = _safe_analyze_word(ws.word)
        ovr = overrides.get(key) or {}
        pos_tag = ovr.get("pos_tag") or analysis["pos_tag"]
        language = ovr.get("language") or "en"
        lang_ready = language_column_ready()
        try:
            feat = ws.features
        except WordFeatures.DoesNotExist:
            feat_kwargs = dict(
                word_state=ws,
                pos_tag=pos_tag,
                syllable_count=analysis["syllable_count"],
                morphological_pattern=analysis.get("morphological_pattern", ""),
                rule_features=analysis.get("rule_features", {}),
                bert_embedding=analysis.get("bert_embedding") or [0.0] * 768,
            )
            if lang_ready:
                feat_kwargs["language"] = language
            WordFeatures.objects.create(**feat_kwargs)
            created += 1
            updated += 1
            continue
        feat.pos_tag = pos_tag
        fields = ["pos_tag"]
        if language_column_ready():
            feat.language = language
            fields.append("language")
        feat.save(update_fields=fields)
        updated += 1
    return {"updated": updated, "created_features": created}


def _normalize_words(words: list) -> list:
    out = []
    for entry in words:
        if isinstance(entry, str):
            out.append({"word": entry.strip().lower(), "rr_augmentation_level": 0})
        elif isinstance(entry, dict):
            item = {
                "word": entry.get("word", "").strip().lower(),
                "rr_augmentation_level": int(entry.get("rr_augmentation_level", 0)),
            }
            if entry.get("pos_tag"):
                item["pos_tag"] = str(entry["pos_tag"]).strip().upper()
            if entry.get("language"):
                item["language"] = str(entry["language"]).strip().lower()
            out.append(item)
    return out


def _safe_analyze_word(word: str) -> dict:
    try:
        return analyze_word(word)
    except Exception:
        return {
            "pos_tag": "OTHER",
            "syllable_count": 1,
            "bert_embedding": [0.0] * 768,
            "morphological_pattern": "",
            "rule_features": {},
        }
