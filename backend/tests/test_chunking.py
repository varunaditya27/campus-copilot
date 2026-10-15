import re

import pytest

from app.core.config import KNOWLEDGE_DIR
from app.rag.chunking import chunk_markdown
from app.rag.tokens import EMBEDDING_WINDOW, count_tokens


def words(text: str) -> int:
    """A deterministic stand-in for token counting, so the tests need no model."""
    return len(text.split())


def chunk(markdown, max_tokens=50, overlap=10, name="doc.md"):
    return chunk_markdown(name, markdown, max_tokens, overlap, count=words)


DOC = """# Library Guide

Intro paragraph about the library.

## Hours

Open on weekdays.

## Borrowing

### Limits

Five books at a time.

### Fines

Five rupees a day.
"""


def test_sections_follow_the_headings_and_carry_their_path():
    chunks = chunk(DOC)
    assert [c.section for c in chunks] == ["Overview", "Hours", "Borrowing > Limits", "Borrowing > Fines"]
    assert [c.index for c in chunks] == [0, 1, 2, 3]
    assert all(c.document == "doc.md" for c in chunks)


def test_each_chunk_starts_with_the_document_and_section():
    first, hours, limits, _ = chunk(DOC)
    assert first.text.startswith("Library Guide\n\nIntro paragraph")
    assert hours.text == "Library Guide - Hours\n\nOpen on weekdays."
    assert limits.prefix == "Library Guide - Borrowing > Limits"
    assert limits.body == "Five books at a time."


def test_a_heading_with_no_text_under_it_makes_no_chunk():
    assert [c.section for c in chunk("# T\n\n## Empty\n\n## Full\n\ntext")] == ["Full"]


def test_a_document_with_no_headings_is_one_overview_chunk():
    chunks = chunk("# T\n\nJust some text.")
    assert [(c.section, c.body) for c in chunks] == [("Overview", "Just some text.")]


def test_an_empty_document_makes_no_chunks():
    assert chunk("") == []


def test_a_heading_inside_a_code_block_is_not_a_heading():
    chunks = chunk("# T\n\n## Real\n\n```text\n## not a heading\nstill code\n```\n\nafter")
    assert [c.section for c in chunks] == ["Real"]
    assert "## not a heading" in chunks[0].body


def long_section(sentences=20):
    return "# T\n\n## Long\n\n" + " ".join(f"Sentence number {i} has exactly seven words." for i in range(sentences))


def test_no_chunk_exceeds_the_limit():
    chunks = chunk(long_section(), max_tokens=40, overlap=10)
    assert len(chunks) > 3
    assert all(words(c.text) <= 40 for c in chunks)


def test_a_long_section_is_split_at_sentence_boundaries():
    for c in chunk(long_section(), max_tokens=40, overlap=0):
        assert c.body.endswith("words.") and c.body.startswith("Sentence")


def test_every_sentence_survives_chunking():
    text = long_section()
    joined = " ".join(c.body for c in chunk(text, max_tokens=40, overlap=10))
    for i in range(20):
        assert f"Sentence number {i} has" in joined


def test_neighbouring_chunks_overlap_by_whole_sentences():
    chunks = chunk(long_section(), max_tokens=40, overlap=16)
    for before, after in zip(chunks, chunks[1:]):
        shared = [s for s in re.findall(r"Sentence number \d+", before.body) if s in after.body]
        assert shared, "consecutive chunks should repeat some text"
        assert words(" ".join(f"{s} has exactly seven words." for s in shared)) <= 16


def test_without_overlap_nothing_repeats():
    bodies = [c.body for c in chunk(long_section(), max_tokens=40, overlap=0)]
    sentences = [s for body in bodies for s in re.findall(r"Sentence number \d+", body)]
    assert len(sentences) == len(set(sentences)) == 20


def test_a_chunk_is_never_only_overlap():
    for c in chunk(long_section(), max_tokens=40, overlap=30):
        assert c.body.strip()
    chunks = chunk(long_section(), max_tokens=40, overlap=30)
    last_sentences = [re.findall(r"Sentence number (\d+)", c.body) for c in chunks]
    assert all(set(b) - set(a) for a, b in zip(last_sentences, last_sentences[1:]))


def test_paragraphs_are_kept_whole_when_they_fit():
    paragraphs = [f"Paragraph {i} " + "word " * 8 for i in range(6)]
    chunks = chunk("# T\n\n## S\n\n" + "\n\n".join(paragraphs), max_tokens=30, overlap=0)
    assert len(chunks) > 1
    for i, paragraph in enumerate(paragraphs):
        holders = [c for c in chunks if f"Paragraph {i} " in c.body]
        assert len(holders) == 1 and paragraph.strip() in holders[0].body


def test_a_table_is_not_cut_in_the_middle_when_it_fits():
    table = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
    chunks = chunk(f"# T\n\n## S\n\n{'filler ' * 30}\n\n{table}\n\n{'more ' * 30}", max_tokens=40, overlap=0)
    holders = [c for c in chunks if "| A | B |" in c.body]
    assert len(holders) == 1 and table in holders[0].body


def test_a_code_block_is_kept_whole_when_it_fits():
    code = "```text\nstep one\n\nstep two\n```"
    chunks = chunk(f"# T\n\n## S\n\n{'filler ' * 30}\n\n{code}\n\n{'more ' * 30}", max_tokens=40, overlap=0)
    assert any(code in c.body for c in chunks)


def test_a_paragraph_too_long_for_one_chunk_falls_back_to_lines_then_sentences_then_words():
    by_lines = chunk("# T\n\n## S\n\n" + "\n".join(f"- item {i} here" for i in range(30)), max_tokens=20, overlap=0)
    assert len(by_lines) > 2 and all(words(c.text) <= 20 for c in by_lines)

    one_giant_word_run = chunk("# T\n\n## S\n\n" + " ".join(f"w{i}" for i in range(100)), max_tokens=20, overlap=0)
    assert len(one_giant_word_run) > 4 and all(words(c.text) <= 20 for c in one_giant_word_run)
    assert " ".join(c.body for c in one_giant_word_run).split() == [f"w{i}" for i in range(100)]


def test_a_word_longer_than_the_limit_is_kept_rather_than_lost():
    chunks = chunk("# T\n\n## S\n\nsupercalifragilistic", max_tokens=1, overlap=0)
    assert any("supercalifragilistic" in c.body for c in chunks)


# --- against the real tokenizer and the real documents


def test_every_chunk_of_the_real_corpus_fits_the_embedding_window():
    for path in sorted(KNOWLEDGE_DIR.glob("**/*.md")):
        if path.name == "README.md":
            continue
        for c in chunk_markdown(path.name, path.read_text(), EMBEDDING_WINDOW, 32):
            assert count_tokens(c.text) <= EMBEDDING_WINDOW, f"{path.name} / {c.section}"


def test_chunking_loses_none_of_the_real_text():
    path = KNOWLEDGE_DIR / "campus" / "library.md"
    joined = re.sub(r"\s+", " ", " ".join(c.body for c in chunk_markdown(path.name, path.read_text(), 128, 32)))
    for sentence in re.findall(r"[A-Z][^.!?\n|#]{30,}[.!?]", path.read_text()):
        assert re.sub(r"\s+", " ", sentence) in joined


def test_the_token_counter_sees_the_models_tokens_not_words():
    assert count_tokens("attendance") >= 1
    assert count_tokens("The minimum attendance requirement is 75% in each course.") == 11
    assert count_tokens("x " * 500) > EMBEDDING_WINDOW  # it does not truncate
