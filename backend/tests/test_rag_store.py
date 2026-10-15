import pytest

from app.rag.chunking import Chunk
from app.rag.store import ChromaStore, KnowledgeBaseNotFound


def chunk(document, index, section, body):
    return Chunk(document=document, section=section, body=body, index=index, prefix=f"{document} - {section}")


def fill(store):
    store.upsert(
        [chunk("library.md", 0, "Hours", "library opens at eight"), chunk("library.md", 1, "Fines", "library fine five rupees per day")],
        file_hash="h1", signature="sig", ingested_at="2026-01-01T00:00:00+00:00",
    )
    store.upsert(
        [chunk("hostel.md", 0, "Mess", "hostel mess dinner timings")],
        file_hash="h2", signature="sig", ingested_at="2026-01-02T00:00:00+00:00",
    )


def test_opening_a_store_that_was_never_built_says_so(chroma_client):
    with pytest.raises(KnowledgeBaseNotFound):
        ChromaStore.open(chroma_client)


def test_a_created_store_can_be_opened_again(chroma_client, store):
    fill(store)
    assert ChromaStore.open(chroma_client).count() == 3


def test_chunks_come_back_with_their_text_and_where_they_came_from(store):
    fill(store)
    chunks = {c.id: c for c in store.all_chunks()}
    assert sorted(chunks) == ["hostel.md::0", "library.md::0", "library.md::1"]
    fines = chunks["library.md::1"]
    assert (fines.document, fines.section) == ("library.md", "Fines")
    assert fines.text == "library.md - Fines\n\nlibrary fine five rupees per day"


def test_search_by_meaning_returns_the_nearest_first_with_distances(store):
    fill(store)
    hits = store.query("library fine per day", 3)
    assert hits[0].id == "library.md::1"
    assert [h.distance for h in hits] == sorted(h.distance for h in hits)
    assert all(h.distance is not None for h in hits)


def test_asking_for_more_than_exist_returns_what_there_is(store):
    fill(store)
    assert len(store.query("anything", 50)) == 3


def test_searching_an_empty_store_returns_nothing(store):
    assert store.query("anything", 5) == [] and store.all_chunks() == []


def test_documents_report_what_was_ingested(store):
    fill(store)
    infos = {d.document: d for d in store.documents()}
    assert infos["library.md"].chunk_count == 2
    assert (infos["library.md"].file_hash, infos["library.md"].signature) == ("h1", "sig")
    assert infos["hostel.md"].ingested_at == "2026-01-02T00:00:00+00:00"


def test_upserting_the_same_ids_replaces_rather_than_duplicates(store):
    fill(store)
    store.upsert([chunk("hostel.md", 0, "Mess", "new text")], "h3", "sig", "2026-02-01T00:00:00+00:00")
    assert store.count() == 3
    assert next(c for c in store.all_chunks() if c.id == "hostel.md::0").text.endswith("new text")


def test_deleting_a_document_removes_only_its_chunks(store):
    fill(store)
    assert store.delete_document("library.md") == 2
    assert [c.document for c in store.all_chunks()] == ["hostel.md"]
    assert store.delete_document("library.md") == 0


def test_reset_empties_the_store(chroma_client, store):
    fill(store)
    fresh = store.reset(chroma_client)
    assert fresh.count() == 0
    fresh.upsert([chunk("a.md", 0, "S", "text")], "h", "s", "t")
    assert fresh.count() == 1


def test_upserting_nothing_is_fine(store):
    store.upsert([], "h", "s", "t")
    assert store.count() == 0


def test_an_index_from_an_older_version_is_readable_and_counts_as_out_of_date(store):
    # The previous ingestion stored only these two fields per chunk.
    store._collection.add(
        ids=["library.md::0"], documents=["old chunk"], metadatas=[{"document": "library.md", "section": "Hours"}]
    )

    (info,) = store.documents()

    assert (info.document, info.file_hash, info.signature, info.chunk_count) == ("library.md", "", "", 1)
