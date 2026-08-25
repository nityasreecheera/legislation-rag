"""Chunking on section boundaries.

Legislative text has structure worth respecting. Every substantive provision
lives under a numbered section ("SEC. 70101. NO TAX ON TIPS."), and that section
number is what a reader would actually cite. So sections are the unit: a chunk
never spans two of them, even when a section is short enough that merging would
pack the context window more efficiently. A chunk that straddles a boundary
produces a citation that points at two provisions at once, which is worse than
a slightly wasteful chunk.

Long sections are windowed internally, splitting on paragraph breaks where
possible so a window rarely begins mid-sentence.

The CEA report has no sections - it is an OCR'd policy paper - so it falls back
to page-level chunks. Its page number is the only citation anchor available.

Two details that took a probe of the corpus to get right:

  * Section headers must be matched at line start with an uppercase "SEC." and a
    5-6 digit number. A looser pattern also catches cross-references to *other*
    statutes ("SEC. 17", "SEC. 1062") and the table of contents, which uses
    lowercase "Sec.".

  * A section number encodes its Title: 5-digit numbers use the first digit
    (10101 -> Title I), 6-digit numbers the first two (100205 -> Title X,
    110001 -> Title XI). Verified against all three bill versions.
"""

from __future__ import annotations

import json
import re
from bisect import bisect_right
from dataclasses import asdict, dataclass
from pathlib import Path

from ingest import load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent

# ~500 tokens at roughly 4 chars/token. Characters rather than tokens because
# chunk sizing does not need tokenizer precision, and a character budget keeps
# ingestion free of an API dependency.
CHUNK_TARGET_CHARS = 2000
CHUNK_OVERLAP_CHARS = 300

# Line-start, uppercase, 5-6 digits. See module docstring.
#
# The whitespace classes are deliberately \s rather than [ \t]: a handful of
# headers are fully justified across the page width, which makes the extractor
# emit a newline between every word ("SEC. \n70102. \nEXTENSION \nAND \n...").
# Requiring a space would silently drop those sections - four of them in the
# enrolled bill alone. \s is safe here because the 5-6 digit constraint already
# excludes cross-references to other statutes ("SEC. 1062") and the uppercase
# match excludes the table of contents, which uses "Sec.".
# Detection only - the heading is read separately from the text that follows.
# Capturing the heading inside this pattern is a trap: a greedy character class
# long enough to hold a real heading also swallows the *next* "SEC." header, and
# because finditer resumes after the previous match, that section disappears
# entirely. Section 50104 was lost exactly this way.
SECTION_HEADER = re.compile(
    r"^[ \t]*(?:\d+[ \t]+)?SEC\.\s+(\d{5,6})\.",
    re.MULTILINE,
)

# Headings run long - the longest in this corpus is 104 characters - so the
# window has to be generous, and the heading ends at its terminating period.
HEADING_MAX_CHARS = 160

# Justified text is hyphenated across line breaks ("RESIL- IENCY"). Rejoining is
# only safe where both halves are uppercase, which is true of headings and not
# of body prose, where a hyphen is more often a real compound ("cost-sharing").
# The draft documents also carry line numbers in the left margin, which land
# inside a hyphenated word when it breaks across lines ("CON- 4 TRIBUTIONS").
LINE_BREAK_HYPHEN = re.compile(r"([A-Z])-\s+(?:\d+\s+)?([A-Z])")

# A heading ends at a period followed by whitespace - but not the period of an
# abbreviation. The lookbehind rejects a period preceded by a single-letter
# token ("U.S.", "H.R."), while leaving ordinary word-final periods alone: the
# "S" of "EXPENSES." is mid-word, so no word boundary precedes it.
HEADING_TERMINATOR = re.compile(r"(?<!\b[A-Z])\.(?=\s|$)")

ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV"]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    # provenance, carried from the manifest
    stage: str | None
    authority: str        # law | proposal | advocacy
    doc_type: str         # statute | analysis
    # location, for citations
    title: str | None     # roman numeral, e.g. "VII"
    section: str | None   # e.g. "70101"
    section_heading: str | None
    page_start: int
    page_end: int
    extraction: str       # "text" | "ocr"
    has_figure: bool


def title_for_section(number: str) -> str | None:
    """Derive the Title a section belongs to from its number."""
    if len(number) == 5:
        index = int(number[0])
    elif len(number) == 6:
        index = int(number[:2])
    else:
        return None
    return ROMAN[index] if 0 < index < len(ROMAN) else None


def _read_heading(text: str, start: int, limit: int) -> str | None:
    """Read a section heading from the text following its "SEC. nnnnn." marker.

    Bounded by the next section's start so a missing terminator cannot run on
    into the following provision.
    """
    window = text[start : min(start + HEADING_MAX_CHARS, limit)]
    window = LINE_BREAK_HYPHEN.sub(r"\1\2", window)
    heading = " ".join(window.split())
    if not heading:
        return None
    match = HEADING_TERMINATOR.search(heading)
    return heading[: match.end()] if match else heading


def _load_pages(doc_id: str) -> list[dict]:
    path = REPO_ROOT / "data" / "extracted" / f"{doc_id}.jsonl"
    with path.open() as fh:
        return [json.loads(line) for line in fh]


def _stitch(pages: list[dict]) -> tuple[str, list[int], list[dict]]:
    """Join pages into one string, keeping a char-offset -> page index."""
    parts, offsets, cursor = [], [], 0
    for page in pages:
        offsets.append(cursor)
        parts.append(page["text"])
        cursor += len(page["text"]) + 1  # +1 for the newline join
    return "\n".join(parts), offsets, pages


def _page_at(offset: int, offsets: list[int], pages: list[dict]) -> dict:
    return pages[max(0, bisect_right(offsets, offset) - 1)]


def _window(text: str) -> list[str]:
    """Split over-long text into overlapping windows on paragraph breaks."""
    if len(text) <= CHUNK_TARGET_CHARS:
        return [text]

    windows, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_TARGET_CHARS, len(text))
        if end < len(text):
            # Prefer a paragraph break in the last third of the window, then a
            # line break, before falling back to a hard cut.
            floor = start + (CHUNK_TARGET_CHARS * 2 // 3)
            for sep in ("\n\n", "\n"):
                found = text.rfind(sep, floor, end)
                if found > start:
                    end = found + len(sep)
                    break
        windows.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARS)

    return [w for w in windows if w]


def chunk_statute(doc_id: str, meta: dict) -> list[Chunk]:
    """Split a bill into per-section chunks, windowing long sections."""
    pages = _load_pages(doc_id)
    text, offsets, pages = _stitch(pages)

    headers = list(SECTION_HEADER.finditer(text))
    chunks: list[Chunk] = []

    # A section number is not unique within a document - the House draft carries
    # SEC. 10012 twice. Occurrences are numbered so chunk_ids stay unique, since
    # retrieval dedup and citation both key on them.
    occurrences: dict[str, int] = {}

    for position, header in enumerate(headers):
        number = header.group(1)
        seen = occurrences.get(number, 0)
        occurrences[number] = seen + 1
        label = number if seen == 0 else f"{number}#{seen + 1}"
        start = header.start()
        end = headers[position + 1].start() if position + 1 < len(headers) else len(text)
        heading = _read_heading(text, header.end(), end)
        body = text[start:end].strip()
        if not body:
            continue

        # Page range is resolved per window, not per section. A 10-page section
        # windowed into 7 chunks must not have all 7 claim the full range - the
        # citation would point a reader at the right provision but the wrong
        # page. `cursor` tracks each window's real offset in the source text.
        cursor = start
        for part, window in enumerate(_window(body)):
            found = text.find(window[:60], cursor, end) if window else -1
            window_start = found if found >= 0 else cursor
            window_end = min(window_start + len(window), end)

            start_page = _page_at(window_start, offsets, pages)
            end_page = _page_at(max(window_start, window_end - 1), offsets, pages)

            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}:{label}:{part}",
                    doc_id=doc_id,
                    text=window,
                    stage=meta.get("stage"),
                    authority=meta["authority"],
                    doc_type=meta["doc_type"],
                    title=title_for_section(number),
                    section=number,
                    section_heading=heading,
                    page_start=start_page["page"],
                    page_end=end_page["page"],
                    extraction=start_page["extraction"],
                    has_figure=start_page["has_figure"],
                )
            )
            cursor = max(cursor + 1, window_end - CHUNK_OVERLAP_CHARS)

    return chunks


def chunk_by_page(doc_id: str, meta: dict) -> list[Chunk]:
    """Fallback for documents with no section structure (the OCR'd report)."""
    chunks: list[Chunk] = []
    for page in _load_pages(doc_id):
        for part, window in enumerate(_window(page["text"].strip())):
            if not window:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_id}:p{page['page']}:{part}",
                    doc_id=doc_id,
                    text=window,
                    stage=meta.get("stage"),
                    authority=meta["authority"],
                    doc_type=meta["doc_type"],
                    title=None,
                    section=None,
                    section_heading=None,
                    page_start=page["page"],
                    page_end=page["page"],
                    extraction=page["extraction"],
                    has_figure=page["has_figure"],
                )
            )
    return chunks


def build_all() -> list[Chunk]:
    chunks: list[Chunk] = []
    for meta in load_manifest().values():
        doc_id = meta["doc_id"]
        if not (REPO_ROOT / "data" / "extracted" / f"{doc_id}.jsonl").exists():
            continue

        if meta["doc_type"] == "statute":
            produced = chunk_statute(doc_id, meta)
        else:
            produced = chunk_by_page(doc_id, meta)

        sections = len({c.section for c in produced if c.section})
        detail = f"{sections} sections" if sections else "page-level"
        print(f"{doc_id:24s} {len(produced):>5} chunks  ({detail})")
        chunks.extend(produced)

    return chunks


def main() -> None:
    chunks = build_all()
    out = REPO_ROOT / "data" / "chunks.jsonl"
    with out.open("w") as fh:
        for chunk in chunks:
            fh.write(json.dumps(asdict(chunk)) + "\n")
    print(f"\n{len(chunks)} chunks -> {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
