import io

from pypdf import PdfReader
from pypdf.errors import PyPdfError


def pdf_to_markdown(data: bytes, title: str) -> str:
    """The text of a PDF as markdown: the title, then a "Page N" section per page
    that has text, so retrieved passages can say which page they came from.

    Raises ValueError if the file cannot be read or has no text layer (a scanned
    document would need OCR)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("The PDF is password protected.")
        pages = [(page.extract_text() or "").strip() for page in reader.pages]
    except (PyPdfError, OSError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError("The file is not a readable PDF.") from exc

    sections = [f"## Page {number}\n\n{text}" for number, text in enumerate(pages, start=1) if text]
    if not sections:
        raise ValueError("The PDF has no text to read. Scanned documents need OCR.")
    return f"# {title}\n\n" + "\n\n".join(sections) + "\n"
