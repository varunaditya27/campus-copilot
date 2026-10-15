import io
import threading
import time

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app
from app.rag import ingest as ingest_module
from app.rag import retriever as retriever_module
from app.rag.retriever import Retriever
from app.rag.store import open_store
from app.services import knowledge_service, rag_eval_service
from fakes import make_pdf
from helpers import ADMIN, FACULTY, STAFF, sign_in_as, sign_up

LIBRARY = "# Library\n\n## Hours\n\nThe library opens at eight.\n"
HOSTEL = "# Hostel\n\n## Mess\n\nDinner at half past seven.\n"


@pytest.fixture
def env(db, chroma_client, tmp_path, monkeypatch):
    curated, uploads = tmp_path / "curated", tmp_path / "uploads"
    curated.mkdir()
    (curated / "library.md").write_text(LIBRARY)
    (curated / "hostel.md").write_text(HOSTEL)
    for module in (knowledge_service, ingest_module):
        monkeypatch.setattr(module, "KNOWLEDGE_DIR", curated)
        monkeypatch.setattr(module, "UPLOAD_DIR", uploads)
    retriever_module.reset_retriever()
    yield type("Env", (), {"curated": curated, "uploads": uploads, "client": chroma_client})
    retriever_module.reset_retriever()


@pytest.fixture
def admin(env):
    return sign_in_as(ADMIN)


def upload(client, filename, data, content_type="application/octet-stream"):
    return client.post("/api/admin/knowledge/upload", files={"file": (filename, data, content_type)})


def status(admin):
    return admin.get("/api/admin/knowledge/status").json()


# --- who may use it

ENDPOINTS = [
    ("post", "/api/admin/knowledge/ingest"),
    ("get", "/api/admin/knowledge/status"),
    ("delete", "/api/admin/knowledge/anything.md"),
    ("post", "/api/admin/rag/eval"),
    ("get", "/api/admin/rag/eval"),
]


@pytest.mark.parametrize("method, path", ENDPOINTS)
def test_only_admins_may_manage_the_knowledge_base(env, method, path):
    for client in (sign_in_as(FACULTY), sign_in_as(STAFF), sign_up(TestClient(app))):
        assert getattr(client, method)(path).status_code == 403
    assert getattr(TestClient(app), method)(path).status_code == 401


def test_uploading_needs_an_admin_too(env):
    student = sign_up(TestClient(app))
    assert upload(student, "x.md", b"# X\n\ntext").status_code == 403
    assert upload(TestClient(app), "x.md", b"# X\n\ntext").status_code == 401
    assert not env.uploads.exists()


# --- ingest and status


def test_status_before_anything_is_built(admin):
    assert status(admin) == {
        "collection": status(admin)["collection"], "built": False, "document_count": 0,
        "chunk_count": 0, "last_ingested_at": None, "documents": [],
    }


def test_ingest_builds_the_knowledge_base(admin):
    report = admin.post("/api/admin/knowledge/ingest").json()
    assert sorted(report["added"]) == ["hostel.md", "library.md"] and report["chunks_written"] == 2

    s = status(admin)
    assert (s["built"], s["document_count"], s["chunk_count"]) == (True, 2, 2)
    assert s["last_ingested_at"] and {d["source"] for d in s["documents"]} == {"curated"}


def test_a_second_ingest_changes_nothing(admin):
    admin.post("/api/admin/knowledge/ingest")
    report = admin.post("/api/admin/knowledge/ingest").json()
    assert sorted(report["unchanged"]) == ["hostel.md", "library.md"] and report["chunks_written"] == 0


def test_a_full_ingest_rebuilds_everything(admin):
    admin.post("/api/admin/knowledge/ingest")
    report = admin.post("/api/admin/knowledge/ingest", params={"full": "true"}).json()
    assert sorted(report["added"]) == ["hostel.md", "library.md"]
    assert status(admin)["document_count"] == 2


def test_ingest_picks_up_an_edited_curated_file(admin, env):
    admin.post("/api/admin/knowledge/ingest")
    (env.curated / "library.md").write_text(LIBRARY.replace("eight", "nine"))
    report = admin.post("/api/admin/knowledge/ingest").json()
    assert report["updated"] == ["library.md"]


def test_only_one_ingest_runs_at_a_time(admin):
    assert knowledge_service._ingest_lock.acquire(blocking=False)
    try:
        response = admin.post("/api/admin/knowledge/ingest")
    finally:
        knowledge_service._ingest_lock.release()
    assert (response.status_code, response.json()["error_code"]) == (409, "ingest_in_progress")
    assert admin.post("/api/admin/knowledge/ingest").status_code == 200


# --- uploading


def test_a_markdown_file_is_added_without_a_rebuild(admin, env):
    admin.post("/api/admin/knowledge/ingest")

    response = upload(admin, "scholarships.md", b"# Scholarships\n\n## Zebra Fund\n\nThe zebra fund pays for stripes.\n")

    assert response.status_code == 201
    body = response.json()
    assert (body["document"], body["chunks"], body["replaced"]) == ("scholarships.md", 1, False)
    assert body["ingest"]["added"] == ["scholarships.md"] and body["ingest"]["unchanged"] != []
    assert (env.uploads / "scholarships.md").read_text().startswith("# Scholarships")
    documents = {d["document"]: d["source"] for d in status(admin)["documents"]}
    assert documents["scholarships.md"] == "uploaded" and documents["library.md"] == "curated"


def test_an_uploaded_document_can_be_searched(admin, env):
    upload(admin, "zoo.md", b"# Zoo Policy\n\n## Zebras\n\nZebra feeding happens on Thursdays.\n")
    search = Retriever(open_store(), rerank=lambda q, texts: [1.0] * len(texts))
    assert search.search("zebra feeding", 1)[0]["document"] == "zoo.md"


def test_uploading_the_same_name_again_replaces_it(admin, env):
    upload(admin, "notes.md", b"# Notes\n\n## A\n\nfirst version words\n")
    again = upload(admin, "notes.md", b"# Notes\n\n## A\n\nsecond version words\n").json()

    assert again["replaced"] is True and again["ingest"]["updated"] == ["notes.md"]
    texts = " ".join(c.text for c in open_store().all_chunks())
    assert "second version" in texts and "first version" not in texts


def test_a_pdf_is_read_and_stored_as_markdown(admin, env):
    response = upload(admin, "Hostel Rules.pdf", make_pdf(["Quiet hours begin at ten", "Guests leave by eight"]))

    assert response.status_code == 201 and response.json()["document"] == "Hostel Rules.md"
    stored = (env.uploads / "Hostel Rules.md").read_text()
    assert "## Page 1" in stored and "Quiet hours begin at ten" in stored and "## Page 2" in stored
    assert not list(env.uploads.glob("*.pdf"))


def test_uppercase_extensions_are_accepted(admin):
    assert upload(admin, "NOTES.MD", b"# T\n\ntext here").json()["document"] == "NOTES.md"


@pytest.mark.parametrize(
    "filename",
    ["../evil.md", "..\\evil.md", "a/b.md", "/etc/passwd.md", ".hidden.md", "README.md", "bad name!.md", "x.exe", "noextension",
     "notes.md.exe", "-flag.md", "a" * 120 + ".md", "tab\tname.md", "semi;colon.md"],
)
def test_hostile_or_odd_file_names_are_refused_and_nothing_is_written(admin, env, filename):
    response = upload(admin, filename, b"# T\n\ntext here")
    assert response.status_code == 422 and response.json()["error_code"] in ("invalid_filename", "unsupported_file_type")
    assert not env.uploads.exists() or not any(env.uploads.iterdir())
    assert not (env.uploads.parent / "evil.md").exists()


def test_an_upload_cannot_overwrite_a_curated_document(admin, env):
    response = upload(admin, "library.md", b"# Library\n\n## Hours\n\nHacked.\n")
    assert (response.status_code, response.json()["error_code"]) == (409, "curated_document_exists")
    assert (env.curated / "library.md").read_text() == LIBRARY
    assert not env.uploads.exists() or not any(env.uploads.iterdir())


def test_files_over_the_size_limit_are_refused(admin, env, monkeypatch):
    monkeypatch.setattr(knowledge_service, "MAX_UPLOAD_BYTES", 2048)
    assert upload(admin, "ok.md", b"# T\n\n" + b"x" * 1000).status_code == 201
    response = upload(admin, "big.md", b"# T\n\n" + b"x" * 5000)
    assert (response.status_code, response.json()["error_code"]) == (413, "file_too_large")
    assert not (env.uploads / "big.md").exists()


def _encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "filename, data",
    [
        ("binary.md", b"\xff\xfe\x00bad"),
        ("empty.md", b""),
        ("blank.md", b"   \n\n  "),
        ("corrupt.pdf", b"this is not a pdf"),
        ("scanned.pdf", make_pdf(["", ""])),
        ("locked.pdf", _encrypted_pdf()),
    ],
)
def test_unreadable_documents_are_refused_and_leave_nothing_behind(admin, env, filename, data):
    admin.post("/api/admin/knowledge/ingest")
    before = status(admin)

    response = upload(admin, filename, data)

    assert (response.status_code, response.json()["error_code"]) == (422, "unreadable_document")
    assert not env.uploads.exists() or not any(env.uploads.iterdir())
    assert status(admin)["chunk_count"] == before["chunk_count"]


def test_a_document_that_makes_no_chunks_is_not_kept(admin, env):
    response = upload(admin, "headings-only.md", b"# Title\n\n## Empty section\n\n## Another\n")
    assert (response.status_code, response.json()["error_code"]) == (422, "unreadable_document")
    assert not (env.uploads / "headings-only.md").exists()
    assert "headings-only.md" not in {d["document"] for d in status(admin)["documents"]}


def test_a_missing_file_field_is_a_validation_error(admin):
    response = admin.post("/api/admin/knowledge/upload", data={"other": "x"})
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


def test_an_upload_waits_its_turn_rather_than_being_lost(admin, env):
    assert knowledge_service._ingest_lock.acquire(blocking=False)
    try:
        response = upload(admin, "late.md", b"# Late\n\n## S\n\nsome text\n")
    finally:
        knowledge_service._ingest_lock.release()
    assert response.status_code == 409
    assert not env.uploads.exists() or not (env.uploads / "late.md").exists()


# --- deleting


def test_deleting_an_uploaded_document_removes_it_everywhere(admin, env):
    upload(admin, "temp.md", b"# Temp\n\n## S\n\nthis is temporary text\n")

    response = admin.delete("/api/admin/knowledge/temp.md")

    assert response.status_code == 200 and response.json() == {"document": "temp.md", "chunks_removed": 1}
    assert not (env.uploads / "temp.md").exists()
    assert "temp.md" not in {d["document"] for d in status(admin)["documents"]}
    assert "temp.md" not in admin.post("/api/admin/knowledge/ingest").json()["added"]


def test_a_curated_document_cannot_be_deleted_through_the_api(admin, env):
    admin.post("/api/admin/knowledge/ingest")
    response = admin.delete("/api/admin/knowledge/library.md")
    assert (response.status_code, response.json()["error_code"]) == (409, "curated_document")
    assert (env.curated / "library.md").exists() and status(admin)["document_count"] == 2


def test_deleting_something_that_is_not_there_is_a_404(admin):
    assert admin.delete("/api/admin/knowledge/nothing.md").status_code == 404


@pytest.mark.parametrize("name", ["..%2Fevil.md", "bad%20name!.md", "x.exe"])
def test_delete_refuses_odd_names(admin, name):
    assert admin.delete(f"/api/admin/knowledge/{name}").status_code in (404, 422)


def test_deleting_leaves_other_documents_searchable(admin, env):
    admin.post("/api/admin/knowledge/ingest")
    upload(admin, "temp.md", b"# Temp\n\n## S\n\ntemporary words\n")
    admin.delete("/api/admin/knowledge/temp.md")
    assert status(admin)["document_count"] == 2


# --- evaluation


class FakeRetriever:
    def __init__(self, gate=None, fail=False):
        self.gate, self.fail = gate, fail

    def search(self, query, n):
        if self.gate:
            self.gate.wait(5)
        if self.fail:
            raise RuntimeError("model exploded")
        return [{"document": "d.md", "section": "s", "snippet": "the answer text", "score": 1.0}]

    def retrieve(self, query, k=3):
        return self.search(query, k)


GOLDEN = {
    "version": 1,
    "questions": [{"id": "a", "question": "q", "facts": [[["d.md", "the answer"]]]}],
    "off_topic": ["x"],
}


@pytest.fixture
def fake_eval(monkeypatch):
    monkeypatch.setattr(rag_eval_service, "load_golden", lambda: GOLDEN)
    rag_eval_service._state.clear()
    rag_eval_service._state["state"] = "idle"

    def install(retriever):
        monkeypatch.setattr(rag_eval_service.retriever, "get_retriever", lambda: retriever)

    yield install
    rag_eval_service._state.clear()
    rag_eval_service._state["state"] = "idle"


def wait_for(admin, state, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = admin.get("/api/admin/rag/eval").json()
        if result["state"] == state:
            return result
        time.sleep(0.02)
    raise AssertionError(f"never reached {state}: {result}")


def test_nothing_has_been_evaluated_yet(admin, fake_eval):
    assert admin.get("/api/admin/rag/eval").json() == {"state": "idle"}


def test_an_evaluation_runs_in_the_background_and_reports(admin, fake_eval):
    fake_eval(FakeRetriever())

    started = admin.post("/api/admin/rag/eval", params={"k": 2})

    assert started.status_code == 202 and started.json()["state"] == "running" and started.json()["k"] == 2
    result = wait_for(admin, "done")
    assert result["report"]["metrics"]["recall@2"] == 1.0 and result["report"]["questions"] == 1
    assert result["finished_at"]


def test_a_second_evaluation_cannot_start_while_one_runs(admin, fake_eval):
    gate = threading.Event()
    fake_eval(FakeRetriever(gate=gate))
    admin.post("/api/admin/rag/eval")
    try:
        second = admin.post("/api/admin/rag/eval")
        assert (second.status_code, second.json()["error_code"]) == (409, "eval_in_progress")
    finally:
        gate.set()
    wait_for(admin, "done")


def test_a_failed_evaluation_says_what_went_wrong(admin, fake_eval):
    fake_eval(FakeRetriever(fail=True))
    admin.post("/api/admin/rag/eval")
    result = wait_for(admin, "failed")
    assert "model exploded" in result["error"]
    assert admin.post("/api/admin/rag/eval").status_code == 202  # and it can be retried
    wait_for(admin, "failed")


@pytest.mark.parametrize("k", [0, 11, -1])
def test_k_must_be_sensible(admin, fake_eval, k):
    assert admin.post("/api/admin/rag/eval", params={"k": k}).status_code == 422
