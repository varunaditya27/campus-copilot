"""Build the Chroma collection from the knowledge/ corpus.

Run with: python -m app.rag.ingest
Re-running is safe — it wipes and rebuilds the collection each time.
"""

import chromadb

from app.core.config import CHROMA_COLLECTION, CHROMA_DIR, KNOWLEDGE_DIR
from app.rag.embeddings import get_embedding_function


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split a markdown document into (section_title, section_body) pairs,
    breaking on level-2 (##) headers. Content before the first ## heading
    (the title and intro) becomes the "Overview" section."""
    sections: list[tuple[str, str]] = []
    title = "Overview"
    body_lines: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if body_lines:
                sections.append((title, "\n".join(body_lines).strip()))
            title = line[3:].strip()
            body_lines = []
        else:
            body_lines.append(line)

    if body_lines:
        sections.append((title, "\n".join(body_lines).strip()))

    return [(t, b) for t, b in sections if b]


def build_collection() -> int:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(name=CHROMA_COLLECTION)
    except Exception:
        pass  # collection didn't exist yet — nothing to clear
    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=get_embedding_function(),
    )

    ids, documents, metadatas = [], [], []
    for md_file in sorted(KNOWLEDGE_DIR.glob("**/*.md")):
        if md_file.name == "README.md":
            continue
        for i, (section, body) in enumerate(split_into_sections(md_file.read_text())):
            ids.append(f"{md_file.name}::{i}")
            documents.append(body)
            metadatas.append({"document": md_file.name, "section": section})

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


if __name__ == "__main__":
    count = build_collection()
    print(f"Ingested {count} chunks into '{CHROMA_COLLECTION}' at {CHROMA_DIR}")
