"""bert_tagger.py — POS tagging and optional BERT embeddings."""

import re

SPACY_TO_APP = {
    "NOUN": "NOUN", "PROPN": "NOUN", "VERB": "VERB", "AUX": "VERB",
    "ADJ": "ADJ", "ADV": "ADV", "PRON": "PRON", "DET": "DET",
    "ADP": "ADP", "CCONJ": "CONJ", "SCONJ": "CONJ", "NUM": "NUM",
}


def tag_word(word: str) -> str:
    w = word.lower().strip()
    if not w:
        return "OTHER"
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            from spacy.cli import download
            download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
        doc = nlp(f"I often think about {w}.")
        for token in doc:
            if token.text.lower() == w:
                return SPACY_TO_APP.get(token.pos_, "OTHER")
        doc2 = nlp(w)
        if doc2:
            return SPACY_TO_APP.get(doc2[0].pos_, "OTHER")
    except Exception:
        pass
    return "OTHER"


def count_syllables(word: str) -> int:
    if not word:
        return 1
    w = re.sub(r"e$", "", word.lower())
    count, prev = 0, False
    for c in w:
        v = c in "aeiouy"
        if v and not prev:
            count += 1
        prev = v
    return max(1, count)


syllables = count_syllables


def get_morph(word: str) -> str:
    return ""


def extract_rule_features(word: str) -> dict:
    return {"visual": {"length": len(word)}}


def get_embedding(word: str) -> list:
    try:
        import torch
        from transformers import AutoTokenizer, AutoModel
        tokenizer = AutoTokenizer.from_pretrained("bert-base-multilingual-cased")
        model = AutoModel.from_pretrained("bert-base-multilingual-cased")
        model.eval()
        inputs = tokenizer(word, return_tensors="pt", truncation=True, max_length=16)
        with torch.no_grad():
            outputs = model(**inputs)
        tokens = outputs.last_hidden_state[0][1:-1]
        if len(tokens) == 0:
            return [0.0] * 768
        return tokens.mean(dim=0).tolist()
    except Exception:
        return [0.0] * 768


def analyze_word(word: str) -> dict:
    if not word:
        return {
            "pos_tag": "OTHER",
            "syllable_count": 1,
            "bert_embedding": [0.0] * 768,
            "morphological_pattern": "",
            "rule_features": {},
        }
    return {
        "pos_tag": tag_word(word),
        "syllable_count": count_syllables(word),
        "bert_embedding": get_embedding(word),
        "morphological_pattern": get_morph(word),
        "rule_features": extract_rule_features(word),
    }
