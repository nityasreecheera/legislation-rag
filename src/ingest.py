"""Page-level extraction from the source PDFs.

Two things make this corpus awkward and shape the design here:

1. One of the four PDFs has no text layer at all - every page is a full-page
   PNG. It cannot be told apart from the others by file extension, so the
   text/OCR decision is made per page at runtime, not per file up front. A real
   corpus can also have a single scanned page inside an otherwise digital
   document; a per-page check handles that for free.

2. Citations have to survive to the end of the pipeline, so page numbers are
   attached at extraction time and carried through every later stage. For the
   OCR'd document, the page number is the *only* anchor available - there is no
   parseable section structure in an image.

Output is one JSONL file per document in data/extracted/, one record per page.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pymupdf
import pytesseract
import yaml
from PIL import Image

# A page with fewer than this many characters is treated as having no usable
# text layer. Chosen by inspection: real text pages in this corpus carry
# 1,100-3,100 chars, while the image-only pages carry 0-1. Anything in between
# is a malformed page we would rather OCR than trust.
TEXT_LAYER_MIN_CHARS = 100

# The source images are 144 DPI. Rendering at 300 does not recover detail that
# is not there, but Tesseract's line segmentation is more reliable on larger
# inputs, and the cost is a few seconds across 27 pages.
OCR_RENDER_DPI = 300

# Figure captions in the CEA report look like "Figure 3-2." - detecting them
# lets us record that a page contains a chart whose data OCR did not capture,
# rather than silently returning axis labels as if they were prose.
FIGURE_CAPTION = re.compile(r"\bFigure\s+\d+[-–]\d+\b", re.IGNORECASE)

# The two draft bills are typeset with line numbers down the left margin. Text
# extraction interleaves them into the prose, which corrupts headings mid-word
# ("COMMUNITY-BASED 13 SERVICES") and fills the lexical index with meaningless
# single-digit tokens. Worse, a heading polluted this way no longer matches its
# counterpart in the other versions, which is what the cross-version grouping
# joins on.
#
# Measured geometry across sample pages: line numbers are numeric tokens at
# x0 = 126 or 133, while body text starts at x0 >= 196. The enrolled bill has no
# numeric token below x0 = 338, so the filter is a no-op there - but it is
# applied only where line numbers are actually detected, so a document that
# happens to place a figure label in the margin is unaffected.
MARGIN_X = 150
MARGIN_DETECT_PAGES = 8
MARGIN_DETECT_MIN_HITS = 20

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Page:
    """One extracted page. `page` is 1-indexed to match how people cite PDFs."""

    doc_id: str
    page: int
    text: str
    extraction: str  # "text" | "ocr"
    char_count: int
    has_figure: bool
    ocr_confidence: float | None = None


def load_manifest(path: Path | None = None) -> dict:
    path = path or REPO_ROOT / "config" / "manifest.yaml"
    with path.open() as fh:
        return yaml.safe_load(fh)["documents"]


def _has_line_numbers(doc: pymupdf.Document) -> bool:
    """Detect a line-numbered left margin by sampling pages from the middle."""
    start = min(doc.page_count // 2, max(0, doc.page_count - MARGIN_DETECT_PAGES))
    hits = 0
    for index in range(start, min(start + MARGIN_DETECT_PAGES, doc.page_count)):
        for word in doc[index].get_text("words"):
            if word[0] < MARGIN_X and word[4].isdigit():
                hits += 1
    return hits >= MARGIN_DETECT_MIN_HITS


def _text_without_margin(page: pymupdf.Page) -> str:
    """Re-assemble page text, dropping numeric tokens in the left margin.

    Words are regrouped by their block and line indices so the line structure
    survives - the section-header pattern depends on headers starting a line.
    """
    lines: dict[tuple[int, int], list[tuple]] = {}
    for word in page.get_text("words"):
        x0, _, _, _, text, block, line, _ = word
        if x0 < MARGIN_X and text.isdigit():
            continue
        lines.setdefault((block, line), []).append(word)

    rendered = []
    for key in sorted(lines):
        words = sorted(lines[key], key=lambda w: w[0])
        rendered.append(" ".join(w[4] for w in words))
    return "\n".join(rendered)


def _ocr_page(page: pymupdf.Page) -> tuple[str, float | None]:
    """Rasterise a page and OCR it, returning text and mean word confidence."""
    pixmap = page.get_pixmap(dpi=OCR_RENDER_DPI)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))

    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

    words, confidences = [], []
    for word, conf in zip(data["text"], data["conf"]):
        if not word.strip():
            continue
        words.append(word)
        # Tesseract reports -1 for entries it did not score.
        if float(conf) >= 0:
            confidences.append(float(conf))

    text = pytesseract.image_to_string(image)
    mean_conf = sum(confidences) / len(confidences) if confidences else None
    return text, mean_conf


def extract_document(pdf_path: Path, doc_id: str) -> list[Page]:
    """Extract every page of one PDF, falling back to OCR where needed."""
    pages: list[Page] = []

    with pymupdf.open(pdf_path) as doc:
        strip_margin = _has_line_numbers(doc)

        for index, page in enumerate(doc):
            raw = _text_without_margin(page) if strip_margin else page.get_text()
            text = raw.strip()

            if len(text) >= TEXT_LAYER_MIN_CHARS:
                extraction, confidence = "text", None
            else:
                text, confidence = _ocr_page(page)
                text = text.strip()
                extraction = "ocr"

            pages.append(
                Page(
                    doc_id=doc_id,
                    page=index + 1,
                    text=text,
                    extraction=extraction,
                    char_count=len(text),
                    has_figure=bool(FIGURE_CAPTION.search(text)),
                    ocr_confidence=confidence,
                )
            )

    return pages


def write_pages(pages: list[Page], out_dir: Path, doc_id: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc_id}.jsonl"
    with out_path.open("w") as fh:
        for page in pages:
            fh.write(json.dumps(asdict(page)) + "\n")
    return out_path


def main() -> None:
    manifest = load_manifest()
    raw_dir = REPO_ROOT / "data" / "raw"
    out_dir = REPO_ROOT / "data" / "extracted"

    for filename, meta in manifest.items():
        doc_id = meta["doc_id"]
        pdf_path = raw_dir / filename
        if not pdf_path.exists():
            print(f"  MISSING {filename}")
            continue

        print(f"{doc_id:24s} extracting ... ", end="", flush=True)
        with pymupdf.open(pdf_path) as probe:
            margin = _has_line_numbers(probe)
        pages = extract_document(pdf_path, doc_id)
        write_pages(pages, out_dir, doc_id)

        ocr_pages = [p for p in pages if p.extraction == "ocr"]
        empty = [p for p in pages if p.char_count == 0]
        summary = f"{len(pages):>4} pages"
        if margin:
            summary += "  [margin line numbers stripped]"
        if ocr_pages:
            confs = [p.ocr_confidence for p in ocr_pages if p.ocr_confidence]
            mean = sum(confs) / len(confs) if confs else 0
            summary += f"  ({len(ocr_pages)} OCR, mean conf {mean:.1f}%)"
        if empty:
            summary += f"  [{len(empty)} empty]"
        print(summary)


if __name__ == "__main__":
    main()
