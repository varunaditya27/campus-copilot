import logging
import os
import re
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path, PurePath

from app.core.config import KNOWLEDGE_COLLECTION, KNOWLEDGE_DIR, UPLOAD_DIR
from app.core.errors import AppError
from app.rag import retriever
from app.rag.embeddings import get_embedding_function
from app.rag.ingest import IngestReport, ingest, knowledge_files
from app.rag.pdf import pdf_to_markdown
from app.rag.store import EmbeddingSettingsChanged, KnowledgeBaseNotFound, create_store, open_store

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Plain file names only: no folders, no dots at the start, no odd characters.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}$")

# One ingest at a time: two at once would both rewrite the same chunks.
_ingest_lock = threading.Lock()


def document_name(filename: str | None) -> str:
    """The name a document is stored under, from an uploaded file's name.

    Raises a 422 for anything that is not a plain .md or .pdf file name. Whatever
    the extension, a document is stored as markdown, so "guide.pdf" becomes "guide.md".
    """
    if not filename or filename != PurePath(filename).name or "\\" in filename:
        raise AppError(422, "invalid_filename", "Use a plain file name, without folders.")
    stem, extension = os.path.splitext(filename)
    if extension.lower() not in (".md", ".pdf"):
        raise AppError(422, "unsupported_file_type", "Only .md and .pdf files can be uploaded.")
    name = f"{stem}.md"
    if not _SAFE_NAME.match(name) or name == "README.md":
        raise AppError(
            422,
            "invalid_filename",
            "File names may use letters, digits, spaces, dots, dashes and underscores, and must not be README.",
        )
    return name


def _curated_names() -> set[str]:
    return {path.name for path in knowledge_files(KNOWLEDGE_DIR)}


@contextmanager
def _exclusive() -> Iterator[None]:
    """Hold the ingest lock, and leave the shared retriever to reopen the store afterwards."""
    if not _ingest_lock.acquire(blocking=False):
        raise AppError(409, "ingest_in_progress", "An ingest is already running. Try again shortly.")
    try:
        yield
    finally:
        retriever.reset_retriever()
        _ingest_lock.release()


def _ingest_now(full: bool = False) -> IngestReport:
    try:
        return ingest(create_store(fresh=full))
    except EmbeddingSettingsChanged as exc:
        raise AppError(409, "embedding_settings_changed", str(exc).replace("python -m app.rag.ingest --full", "run a full rebuild")) from exc


def run_ingest(full: bool = False) -> IngestReport:
    """Bring the knowledge base up to date with the curated corpus and the uploads."""
    with _exclusive():
        return _ingest_now(full)


def _markdown_from_upload(name: str, filename: str, data: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        try:
            return pdf_to_markdown(data, title=Path(name).stem)
        except ValueError as exc:
            raise AppError(422, "unreadable_document", str(exc)) from exc
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AppError(422, "unreadable_document", "The file is not UTF-8 text.") from exc
    if not text.strip():
        raise AppError(422, "unreadable_document", "The file is empty.")
    return text


def save_upload(filename: str | None, data: bytes) -> dict:
    """Add (or replace) a document from an uploaded .md or .pdf file, and ingest it."""
    name = document_name(filename)
    if name in _curated_names():
        raise AppError(
            409,
            "curated_document_exists",
            f"'{name}' is part of the curated corpus. Edit the file in the repository and ingest again.",
        )
    markdown = _markdown_from_upload(name, filename, data)

    with _exclusive():
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        target = UPLOAD_DIR / name
        replaced = target.exists()
        # Write to a temporary file and rename, so a crash never leaves half a document.
        with tempfile.NamedTemporaryFile("w", dir=UPLOAD_DIR, suffix=".tmp", delete=False, encoding="utf-8") as handle:
            handle.write(markdown)
        os.replace(handle.name, target)

        report = _ingest_now()
        chunks = next((d.chunk_count for d in open_store().documents() if d.document == name), 0)
        if chunks == 0:
            target.unlink(missing_ok=True)
            _ingest_now()
            raise AppError(422, "unreadable_document", "No searchable text was found in the document.")
    return {"document": name, "chunks": chunks, "replaced": replaced, "ingest": asdict(report)}


def status() -> dict:
    curated = _curated_names()
    try:
        infos = open_store().documents()
    except KnowledgeBaseNotFound:
        infos = []
    documents = [
        {
            "document": info.document,
            "chunks": info.chunk_count,
            "ingested_at": info.ingested_at or None,
            "source": "curated" if info.document in curated else "uploaded",
        }
        for info in infos
    ]
    stamps = [d["ingested_at"] for d in documents if d["ingested_at"]]
    return {
        "collection": KNOWLEDGE_COLLECTION,
        "built": bool(infos),
        "document_count": len(documents),
        "chunk_count": sum(d["chunks"] for d in documents),
        "last_ingested_at": max(stamps) if stamps else None,
        "documents": documents,
    }


def delete_document(filename: str) -> dict:
    """Remove an uploaded document and its chunks. Curated documents are managed in
    the repository, so they cannot be removed here."""
    name = document_name(filename)
    if name in _curated_names():
        raise AppError(
            409,
            "curated_document",
            f"'{name}' is part of the curated corpus. Delete the file in the repository and ingest again.",
        )
    with _exclusive():
        try:
            removed = open_store().delete_document(name)
        except KnowledgeBaseNotFound:
            removed = 0
        target = UPLOAD_DIR / name
        existed = target.exists()
        target.unlink(missing_ok=True)
    if not removed and not existed:
        raise AppError(404, "not_found", f"No document named '{name}'.")
    return {"document": name, "chunks_removed": removed}



def document_chunks(name: str) -> dict:
    """The chunks one document was split into, as they sit in the store."""
    try:
        store = open_store()
        infos = {d.document: d for d in store.documents()}
        chunks = [c for c in store.all_chunks() if c.document == name]
    except KnowledgeBaseNotFound:
        infos, chunks = {}, []
    if name not in infos or not chunks:
        raise AppError(404, "not_found", f"No document named '{name}' in the knowledge base.")
    info = infos[name]
    embedding = get_embedding_function()
    return {
        "document": name,
        "source": "curated" if name in _curated_names() else "uploaded",
        "ingested_at": info.ingested_at or None,
        "chunk_count": len(chunks),
        "embedding": {"model": embedding.identity, "dimensions": embedding.dimensions, "collection": KNOWLEDGE_COLLECTION},
        "chunks": [
            {"id": c.id, "section": c.section, "characters": len(c.text), "words": len(c.text.split()), "text": c.text}
            for c in sorted(chunks, key=lambda c: c.id)
        ],
    }
