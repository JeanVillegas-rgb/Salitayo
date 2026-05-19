from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class CorpusDocument:
    title: str
    content: str


class RagCorpus:
    def __init__(self, corpus_dir: Path):
        self.corpus_dir = corpus_dir
        self._documents = None

    def load(self):
        if self._documents is not None:
            return self._documents

        documents = []
        if self.corpus_dir.exists():
            for path in sorted(self.corpus_dir.glob("*.md")):
                documents.append(
                    CorpusDocument(
                        title=path.stem.replace("_", " ").title(),
                        content=path.read_text(encoding="utf-8"),
                    )
                )
        self._documents = documents
        return documents

    def retrieve(self, query: str, limit: int = 3):
        query_tokens = set(re.findall(r"[A-Za-z][A-Za-z\-]+", query.lower()))
        scored_documents = []

        for document in self.load():
            content_tokens = set(
                re.findall(r"[A-Za-z][A-Za-z\-]+", document.content.lower())
            )
            score = len(query_tokens & content_tokens)
            scored_documents.append((score, document))

        scored_documents.sort(key=lambda item: item[0], reverse=True)
        return [document for score, document in scored_documents[:limit] if score > 0]
