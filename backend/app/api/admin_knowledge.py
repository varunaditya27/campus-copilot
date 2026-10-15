from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Query, UploadFile

from app.api.deps import AdminUser
from app.core.errors import AppError
from app.services import knowledge_service, rag_eval_service

router = APIRouter(prefix="/api/admin", tags=["admin"])

READ_CHUNK = 1024 * 1024


@router.post("/knowledge/ingest")
def ingest(admin: AdminUser, full: bool = False) -> dict:
    """Bring the knowledge base up to date. Only changed documents are redone,
    unless full=true, which wipes the store and rebuilds everything."""
    return asdict(knowledge_service.run_ingest(full))


@router.post("/knowledge/upload", status_code=201)
def upload(admin: AdminUser, file: UploadFile) -> dict:
    """Add a .md or .pdf document without a full rebuild. Uploading a name that
    was uploaded before replaces it."""
    data = bytearray()
    while chunk := file.file.read(READ_CHUNK):
        data += chunk
        if len(data) > knowledge_service.MAX_UPLOAD_BYTES:
            raise AppError(
                413, "file_too_large", f"Files can be at most {knowledge_service.MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
            )
    return knowledge_service.save_upload(file.filename, bytes(data))


@router.get("/knowledge/status")
def status(admin: AdminUser) -> dict:
    return knowledge_service.status()


@router.get("/knowledge/{document_name}/chunks")
def chunks(document_name: str, admin: AdminUser) -> dict:
    """What a document was split into, with the embedding settings, for checking what the assistant can find."""
    return knowledge_service.document_chunks(document_name)


@router.delete("/knowledge/{document_name}")
def delete(document_name: str, admin: AdminUser) -> dict:
    return knowledge_service.delete_document(document_name)


@router.post("/rag/eval", status_code=202)
def start_evaluation(admin: AdminUser, k: Annotated[int, Query(ge=1, le=10)] = 3) -> dict:
    """Start scoring retrieval against the golden questions. Takes about a minute;
    read the outcome from GET /api/admin/rag/eval."""
    return rag_eval_service.start(k)


@router.get("/rag/eval")
def evaluation_result(admin: AdminUser) -> dict:
    return rag_eval_service.current()
