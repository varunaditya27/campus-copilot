import re
from collections.abc import Callable
from dataclasses import dataclass

from app.rag.tokens import count_tokens

_HEADING = re.compile(r"^(#{2,3}) +(.*\S)\s*$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_TABLE_ROW = re.compile(r"^\s*\|")


@dataclass(frozen=True)
class Chunk:
    document: str  # file name, e.g. "library.md"
    section: str  # heading path, e.g. "Facilities > Quiet Study Area"
    body: str
    index: int  # position within the document
    prefix: str = ""  # "Document title - section", so a chunk makes sense on its own

    @property
    def text(self) -> str:
        """What is embedded, indexed and shown: the context line, then the body."""
        return f"{self.prefix}\n\n{self.body}" if self.prefix else self.body


def _sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """The document title and its (heading path, body) sections, split on ## and ###."""
    title = ""
    sections: list[tuple[str, list[str]]] = [("Overview", [])]
    parent = ""
    in_code = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        heading = None if in_code else _HEADING.match(line)
        if not in_code and line.startswith("# ") and not title:
            title = line[2:].strip()
        elif heading:
            level, name = len(heading.group(1)), heading.group(2).strip()
            if level == 2:
                parent, path = name, name
            else:
                path = f"{parent} > {name}" if parent else name
            sections.append((path, []))
        else:
            sections[-1][1].append(line)
    return title, [(path, "\n".join(lines).strip()) for path, lines in sections if "".join(lines).strip()]


def _blocks(body: str) -> list[str]:
    """Paragraphs, with code fences and tables kept whole."""
    blocks: list[str] = []
    current: list[str] = []
    in_code = False
    for line in body.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if not line.strip() and not in_code:
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _expand(text: str, budget: int, count: Callable[[str], int]) -> list[tuple[str, str]]:
    """Cut an over-long block into (piece, separator-that-followed-it) units of at
    most `budget` tokens: by lines first, then sentences, then words."""
    if count(text) <= budget:
        return [(text, "")]
    for splitter, separator in ((lambda t: t.split("\n"), "\n"), (_SENTENCE_END.split, " "), (lambda t: t.split(" "), " ")):
        parts = [p for p in splitter(text) if p.strip()]
        if len(parts) > 1:
            units: list[tuple[str, str]] = []
            for part in parts:
                units += [(t, s or separator) for t, s in _expand(part, budget, count)]
            return units
    return [(text, "")]  # a single word longer than the budget: leave it whole


def _pack(units: list[tuple[str, str]], budget: int, overlap: int, count: Callable[[str], int]) -> list[str]:
    """Group units into chunks of at most `budget` tokens. Each chunk after the
    first starts with whole units from the end of the previous one, up to
    `overlap` tokens, so a sentence cut at a boundary appears in both."""

    def join(group: list[tuple[str, str]]) -> str:
        return "".join(text + sep for text, sep in group).rstrip()

    chunks: list[str] = []
    group: list[tuple[str, str]] = []
    fresh = 0  # units in `group` that are not carried-over overlap
    for unit in units:
        if group and count(join(group + [unit])) > budget:
            if fresh:
                chunks.append(join(group))
            carried: list[tuple[str, str]] = []
            for earlier in reversed(group):
                if count(join([earlier] + carried)) > overlap:
                    break
                carried.insert(0, earlier)
            group, fresh = carried, 0
            # If the carried-over text leaves no room for the new unit, drop it.
            if group and count(join(group + [unit])) > budget:
                group = []
        group.append(unit)
        fresh += 1
    if fresh:
        chunks.append(join(group))
    return chunks


def chunk_markdown(
    document: str,
    markdown: str,
    max_tokens: int,
    overlap_tokens: int,
    count: Callable[[str], int] = count_tokens,
) -> list[Chunk]:
    """Split a markdown document into chunks no longer than max_tokens.

    Chunks follow the document's headings, so a chunk never mixes two sections,
    and each carries its heading path. Within a long section, paragraphs, tables
    and code blocks are kept whole where they fit.
    """
    title, sections = _sections(markdown)
    chunks: list[Chunk] = []
    for path, body in sections:
        prefix = f"{title} - {path}" if title and path != "Overview" else (title or path)
        budget = max_tokens - count(prefix + "\n\n")
        units: list[tuple[str, str]] = []
        for block in _blocks(body):
            units += [(t, s or "\n\n") for t, s in _expand(block, budget, count)]
        for piece in _pack(units, budget, overlap_tokens, count):
            chunks.append(Chunk(document=document, section=path, body=piece, index=len(chunks), prefix=prefix))
    return chunks
