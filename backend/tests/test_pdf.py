import io

import pytest
from pypdf import PdfWriter

from app.rag.pdf import pdf_to_markdown
from fakes import make_pdf


def test_each_page_with_text_becomes_a_numbered_section():
    markdown = pdf_to_markdown(make_pdf(["First page text", "Second page text"]), title="Guide")
    assert markdown.startswith("# Guide\n\n## Page 1\n\nFirst page text")
    assert "## Page 2\n\nSecond page text" in markdown


def test_pages_without_text_are_skipped_but_numbering_stays_true():
    markdown = pdf_to_markdown(make_pdf(["One", "", "Three"]), title="T")
    assert "## Page 1" in markdown and "## Page 3" in markdown and "## Page 2" not in markdown


def test_text_with_brackets_survives():
    assert "Fee (per year) is 5" in pdf_to_markdown(make_pdf(["Fee (per year) is 5"]), title="T")


def test_a_pdf_with_no_text_layer_is_refused_with_a_hint_about_ocr():
    with pytest.raises(ValueError, match="OCR"):
        pdf_to_markdown(make_pdf(["", ""]), title="T")


@pytest.mark.parametrize("data", [b"", b"not a pdf at all", b"%PDF-1.4\ngarbage", b"\x00" * 100])
def test_unreadable_files_are_refused(data):
    with pytest.raises(ValueError, match="not a readable PDF"):
        pdf_to_markdown(data, title="T")


def test_a_password_protected_pdf_is_refused():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(ValueError, match="password"):
        pdf_to_markdown(buffer.getvalue(), title="T")
