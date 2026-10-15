"""Build and update the vector store from the knowledge/ corpus.

Run with: python -m app.rag.ingest [--full]

Only documents that changed since the last run are re-embedded. --full wipes
the store and rebuilds everything, which is needed after changing the chunking
settings or the embedding model if the store holds chunks made the old way
(the run detects that on its own too, but --full is the blunt tool).
"""

import argparse
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import CHROMA_COLLECTION, CHROMA_DIR, KNOWLEDGE_DIR
from app.rag.chunking import Chunk, chunk_markdown
from app.rag.store import ChromaStore, get_client

logger = logging.getLogger(__name__)

# Chunks of at most 256 tokens, the most the embedding model reads (it cuts off
# anything longer), with 32 tokens repeated between neighbouring chunks of a
# long section. On this corpus 256 scored as well as or better than the other
# sizes tried (see rag_eval/history.jsonl).
CHUNK_TOKENS = 256
CHUNK_OVERLAP = 32

# Bump when the chunking code changes in a way that changes its output.
CHUNKER_VERSION = 1
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Stored with every document. A document is re-ingested when its file or this
# signature changes, so changed settings never leave stale chunks behind.
SIGNATURE = f"chunker{CHUNKER_VERSION}:{CHUNK_TOKENS}:{CHUNK_OVERLAP}:{EMBEDDING_MODEL}"


@dataclass
class IngestReport:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    chunks_written: int = 0
    duplicates_skipped: int = 0
    seconds: float = 0.0

    def summary(self) -> str:
        return (
            f"{len(self.added)} added, {len(self.updated)} updated, {len(self.removed)} removed, "
            f"{len(self.unchanged)} unchanged; {self.chunks_written} chunks written, "
            f"{self.duplicates_skipped} duplicate chunks skipped, {self.seconds:.1f}s"
        )


def knowledge_files(directory: Path = KNOWLEDGE_DIR) -> list[Path]:
    return [p for p in sorted(directory.glob("**/*.md")) if p.name != "README.md"]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fingerprint(text: str) -> str:
    return hashlib.sha256(re.sub(r"\s+", " ", text).strip().lower().encode()).hexdigest()


def ingest_file(store: ChromaStore, path: Path, seen: set[str], report: IngestReport) -> None:
    """Replace a document's chunks with freshly made ones."""
    chunks: list[Chunk] = []
    for chunk in chunk_markdown(path.name, path.read_text(), CHUNK_TOKENS, CHUNK_OVERLAP):
        fingerprint = _fingerprint(chunk.text)
        if fingerprint in seen:
            report.duplicates_skipped += 1
            continue
        seen.add(fingerprint)
        chunks.append(chunk)

    store.delete_document(path.name)
    store.upsert(chunks, file_hash(path), SIGNATURE, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    report.chunks_written += len(chunks)


def ingest(store: ChromaStore, directory: Path = KNOWLEDGE_DIR) -> IngestReport:
    """Bring the store in line with the files in `directory`."""
    started = time.monotonic()
    report = IngestReport()
    known = {info.document: info for info in store.documents()}
    seen: set[str] = set()
    files = knowledge_files(directory)

    for path in files:
        info = known.get(path.name)
        if info and info.file_hash == file_hash(path) and info.signature == SIGNATURE:
            report.unchanged.append(path.name)
            logger.info("unchanged: %s", path.name)
            continue
        ingest_file(store, path, seen, report)
        (report.updated if info else report.added).append(path.name)
        logger.info("%s: %s", "updated" if info else "added", path.name)

    present = {p.name for p in files}
    for name in sorted(set(known) - present):
        store.delete_document(name)
        report.removed.append(name)
        logger.info("removed: %s", name)

    report.seconds = time.monotonic() - started
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build or update the knowledge base.")
    parser.add_argument("--full", action="store_true", help="wipe the store and rebuild everything")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    client = get_client()
    store = ChromaStore.create(client)
    if args.full:
        store = store.reset(client)
    report = ingest(store)
    print(f"Knowledge base '{CHROMA_COLLECTION}' at {CHROMA_DIR}: {report.summary()}")


if __name__ == "__main__":
    main()
