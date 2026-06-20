"""RAG corpus loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    id: str
    text: str
    source: str


def load_corpus(corpus_path: str | Path) -> list[Document]:
    path = Path(corpus_path)
    if not path.exists():
        raise FileNotFoundError(f"RAG corpus not found: {path}")
    docs: list[Document] = []
    if path.is_file():
        docs.append(Document(id=path.stem, text=path.read_text(encoding="utf-8"), source=str(path)))
        return docs
    for i, fp in enumerate(sorted(path.rglob("*.txt")) + sorted(path.rglob("*.md"))):
        docs.append(Document(id=f"doc-{i}", text=fp.read_text(encoding="utf-8"), source=str(fp)))
    if not docs:
        raise ValueError(f"No .txt or .md documents found in {path}")
    return docs
