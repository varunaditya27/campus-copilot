import pytest

from app.rag import ingest as ingest_module
from app.rag.ingest import ingest, knowledge_files
from helpers import insert_legacy_chunks


def write(directory, name, text):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


LIBRARY = "# Library\n\n## Hours\n\nOpen at eight.\n\n## Fines\n\nFive rupees a day.\n"
HOSTEL = "# Hostel\n\n## Mess\n\nDinner at half past seven.\n"


@pytest.fixture
def corpus(tmp_path):
    write(tmp_path, "campus/library.md", LIBRARY)
    write(tmp_path, "campus/hostel.md", HOSTEL)
    write(tmp_path, "README.md", "# Readme\n\n## Not knowledge\n\nIgnore me.\n")
    return tmp_path


def test_the_first_run_adds_every_document_but_the_readme(store, corpus):
    report = ingest(store, corpus)

    assert sorted(report.added) == ["hostel.md", "library.md"]
    assert report.updated == report.removed == report.unchanged == []
    assert report.chunks_written == 3 == store.count()
    assert {d.document for d in store.documents()} == {"hostel.md", "library.md"}


def test_nested_folders_are_searched(store, tmp_path):
    write(tmp_path, "a/b/c/deep.md", "# Deep\n\n## S\n\ntext\n")
    assert [p.name for p in knowledge_files(tmp_path)] == ["deep.md"]


def test_a_second_run_changes_nothing(store, corpus):
    ingest(store, corpus)
    before = {d.document: d.ingested_at for d in store.documents()}

    report = ingest(store, corpus)

    assert sorted(report.unchanged) == ["hostel.md", "library.md"]
    assert report.added == report.updated == report.removed == []
    assert report.chunks_written == 0
    assert {d.document: d.ingested_at for d in store.documents()} == before


def test_only_the_edited_document_is_redone(store, corpus):
    ingest(store, corpus)
    write(corpus, "campus/library.md", LIBRARY.replace("eight", "nine"))

    report = ingest(store, corpus)

    assert report.updated == ["library.md"] and report.unchanged == ["hostel.md"]
    texts = " ".join(c.text for c in store.all_chunks())
    assert "nine" in texts and "eight" not in texts


def test_chunks_that_no_longer_exist_in_an_edited_document_are_removed(store, corpus):
    ingest(store, corpus)
    write(corpus, "campus/library.md", "# Library\n\n## Hours\n\nOpen at eight.\n")

    ingest(store, corpus)

    assert [c.id for c in store.all_chunks() if c.document == "library.md"] == ["library.md::0"]


def test_a_deleted_file_is_removed_from_the_store(store, corpus):
    ingest(store, corpus)
    (corpus / "campus" / "hostel.md").unlink()

    report = ingest(store, corpus)

    assert report.removed == ["hostel.md"]
    assert {c.document for c in store.all_chunks()} == {"library.md"}


def test_a_new_file_is_added_later(store, corpus):
    ingest(store, corpus)
    write(corpus, "new.md", "# New\n\n## S\n\nfresh\n")
    report = ingest(store, corpus)
    assert report.added == ["new.md"] and "new.md" in {d.document for d in store.documents()}


def test_changed_chunking_settings_redo_documents_whose_files_did_not_change(store, corpus, monkeypatch):
    ingest(store, corpus)
    monkeypatch.setattr(ingest_module, "current_signature", lambda: "chunker2:128:16:all-MiniLM-L6-v2")

    report = ingest(store, corpus)

    assert sorted(report.updated) == ["hostel.md", "library.md"] and report.unchanged == []
    assert {d.signature for d in store.documents()} == {"chunker2:128:16:all-MiniLM-L6-v2"}


def test_identical_chunks_are_stored_once(store, tmp_path):
    same = "# Same\n\n## Part\n\nExactly the same words here.\n"
    write(tmp_path, "one.md", same)
    write(tmp_path, "two.md", same)

    report = ingest(store, tmp_path)

    assert report.duplicates_skipped == 1 and store.count() == 1


def test_a_full_rebuild_starts_from_nothing(store, corpus):
    ingest(store, corpus)
    fresh = store.reset()
    assert fresh.count() == 0
    assert sorted(ingest(fresh, corpus).added) == ["hostel.md", "library.md"]


def test_the_summary_describes_the_run(store, corpus):
    summary = ingest(store, corpus).summary()
    assert "2 added" in summary and "3 chunks written" in summary


def test_an_index_from_an_older_version_is_brought_up_to_date(store, corpus):
    insert_legacy_chunks(
        store,
        [
            ("library.md::0", "old chunk one", "library.md", "Hours"),
            ("library.md::1", "old chunk two", "library.md", "Fines"),
            ("gone.md::0", "old chunk of a deleted file", "gone.md", "S"),
        ],
    )

    report = ingest(store, corpus)

    assert report.updated == ["library.md"] and report.added == ["hostel.md"] and report.removed == ["gone.md"]
    texts = " ".join(c.text for c in store.all_chunks())
    assert "old chunk" not in texts and "Open at eight" in texts
