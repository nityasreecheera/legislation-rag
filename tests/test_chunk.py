"""Tests for section detection and chunking.

The first two cases are regressions. Both bugs were silent - they produced a
smaller corpus rather than an error, and would only have surfaced as a question
the pipeline inexplicably could not answer.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from chunk import (  # noqa: E402
    CHUNK_TARGET_CHARS,
    SECTION_HEADER,
    _read_heading,
    _window,
    title_for_section,
)


class TestSectionDetection:
    def test_justified_header_is_matched(self):
        """Justified headers put a newline between every word.

        "SEC. \\n70102. \\nEXTENSION \\nAND ..." - requiring a space between
        "SEC." and the number silently dropped four sections of the enrolled
        bill.
        """
        text = "SEC. \n70102. \nEXTENSION \nAND \nENHANCEMENT.\n"
        assert [m.group(1) for m in SECTION_HEADER.finditer(text)] == ["70102"]

    def test_consecutive_headers_are_both_found(self):
        """A heading capture wide enough to hold a real heading also swallows
        the following header, because finditer resumes after the match. Section
        50104 disappeared exactly this way."""
        text = (
            "SEC. 50103. ROYALTIES ON EXTRACTED METHANE.\n"
            "Section 50263 of Public Law 117-169 (30 U.S.C. 1727) is repealed.\n"
            "SEC. 50104. ALASKA OIL AND GAS LEASING.\n"
            "(a) DEFINITIONS.\n"
        )
        assert [m.group(1) for m in SECTION_HEADER.finditer(text)] == ["50103", "50104"]

    @pytest.mark.parametrize(
        "text",
        [
            "of section 1062. of the Act",  # cross-reference, not a header
            "Sec. 70201. No tax on tips.",  # table of contents uses lowercase
            "SEC. 17. SHORT TITLE.",  # too few digits to be this bill's own
        ],
    )
    def test_non_headers_are_rejected(self, text):
        assert not SECTION_HEADER.findall(text)

    def test_line_numbered_draft_header_is_matched(self):
        """House and Senate drafts carry line numbers in the left margin."""
        assert SECTION_HEADER.findall("  12  SEC. 110101. NO TAX ON TIPS.") == ["110101"]


class TestHeadingExtraction:
    def test_stops_at_terminating_period(self):
        text = "SEC. 10104. RESTRICTIONS ON INTERNET EXPENSES.\n(a) In general..."
        heading = _read_heading(text, text.index(".", 5) + 1, len(text))
        assert heading == "RESTRICTIONS ON INTERNET EXPENSES."

    def test_rejoins_line_break_hyphenation(self):
        """Justification splits words: "RESIL- IENCY" is one word."""
        text = " MUNITIONS AND DEFENSE SUPPLY CHAIN RESIL- IENCY.\nBody text."
        assert _read_heading(text, 0, len(text)).endswith("RESILIENCY.")

    def test_does_not_split_on_abbreviation(self):
        text = " AMENDMENTS TO 30 U.S.C. 1727 AND RELATED LAW.\nBody."
        assert _read_heading(text, 0, len(text)) == (
            "AMENDMENTS TO 30 U.S.C. 1727 AND RELATED LAW."
        )


class TestTitleMapping:
    @pytest.mark.parametrize(
        "section,expected",
        [
            ("10101", "I"),      # 5 digits -> first digit
            ("70201", "VII"),
            ("90103", "IX"),
            ("100205", "X"),     # 6 digits -> first two digits
            ("110101", "XI"),    # House-only title
        ],
    )
    def test_section_number_encodes_title(self, section, expected):
        assert title_for_section(section) == expected

    def test_same_provision_maps_to_different_titles_across_versions(self):
        """The reason citations must name their document. "No tax on tips" is
        Title VII in the enrolled bill and Title XI in the House version."""
        assert title_for_section("70201") != title_for_section("110101")

    def test_unparseable_number_returns_none(self):
        assert title_for_section("17") is None


class TestWindowing:
    def test_short_text_is_not_split(self):
        text = "A short section." * 5
        assert _window(text) == [text]

    def test_windows_respect_the_size_budget(self):
        text = "\n\n".join(f"Paragraph {i} " + "word " * 60 for i in range(40))
        assert all(len(w) <= CHUNK_TARGET_CHARS for w in _window(text))

    def test_windows_cover_the_whole_text(self):
        """Overlapping windows must not drop content between them."""
        text = "\n\n".join(f"UNIQUE{i} " + "filler " * 50 for i in range(30))
        joined = "".join(_window(text))
        for i in range(30):
            assert f"UNIQUE{i}" in joined

    def test_windows_terminate_on_unsplittable_text(self):
        """No paragraph or line breaks to split on - must still terminate."""
        assert len(_window("x" * (CHUNK_TARGET_CHARS * 3))) >= 3


class TestChunkInvariants:
    """Properties that must hold over the built corpus, if it has been built."""

    @pytest.fixture(scope="class")
    def chunks(self):
        import json

        path = Path(__file__).resolve().parent.parent / "data" / "chunks.jsonl"
        if not path.exists():
            pytest.skip("corpus not built; run src/chunk.py")
        with path.open() as fh:
            return [json.loads(line) for line in fh]

    def test_every_chunk_carries_provenance(self, chunks):
        """Nothing may reach retrieval without an authority label - that field
        is what stops a House proposal being answered as current law."""
        assert all(c["authority"] in {"law", "proposal", "advocacy"} for c in chunks)

    def test_statute_chunks_are_citable(self, chunks):
        """A statute chunk must resolve to a section and a location.

        Not to a Title: federal bills divide into Titles I-XI and encode that in
        the section number, but Arizona bills have no such division. Requiring a
        Title here would be asserting a federal convention on a state document.
        """
        for c in chunks:
            if c["doc_type"] == "statute":
                assert c["section"] and c["page_start"], c["chunk_id"]

    def test_federal_statutes_carry_a_title(self, chunks):
        for c in chunks:
            if c["doc_type"] == "statute" and c["jurisdiction"] == "federal":
                assert c["title"], c["chunk_id"]

    def test_only_versions_of_one_bill_share_a_version_group(self, chunks):
        """Grouping collapses provisions across versions of the same bill.

        Arizona bills are separate bills, not versions of each other, so they
        must not share a group - otherwise "Short title" in one would be
        presented as a variant of "Short title" in another.
        """
        groups = {}
        for c in chunks:
            groups.setdefault(c["version_group"], set()).add(c["doc_id"])
        assert groups.get("hr1") == {
            "hr1-enrolled", "hr1-senate-substitute", "hr1-house-passed"
        }
        for doc in groups.get(None, set()):
            assert doc.startswith("az-") or doc == "cea-report"

    def test_chunk_ids_are_unique(self, chunks):
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_page_ranges_are_ordered(self, chunks):
        assert all(c["page_start"] <= c["page_end"] for c in chunks)

    def test_no_chunk_spans_two_sections(self, chunks):
        """A chunk containing a second section header would produce a citation
        pointing at two provisions at once."""
        for c in chunks:
            if not c["section"]:
                continue
            found = SECTION_HEADER.findall(c["text"])
            assert set(found) <= {c["section"]}, c["chunk_id"]

    def test_ocr_document_is_page_anchored(self, chunks):
        ocr = [c for c in chunks if c["extraction"] == "ocr"]
        assert ocr, "expected the CEA report to be OCR'd"
        assert all(c["page_start"] == c["page_end"] for c in ocr)


class TestStateSectionDetection:
    """Arizona bills number sections plainly, not with the federal 5-digit form."""

    def test_state_headers_are_matched(self):
        from chunk import STATE_SECTION_HEADER

        text = "Section 1. Title 9, chapter 4 is amended\nSec. 2. Short title\n"
        assert STATE_SECTION_HEADER.findall(text) == ["1", "2"]

    def test_federal_pattern_would_miss_them(self):
        """Why the style is a manifest field rather than one shared regex."""
        assert not SECTION_HEADER.findall("Section 1. Title 9 is amended")

    def test_state_pattern_is_case_insensitive(self):
        from chunk import STATE_SECTION_HEADER

        assert STATE_SECTION_HEADER.findall("SECTION 3. Effective date") == ["3"]


class TestWebExtraction:
    def test_mhtml_container_is_decoded(self):
        """MHTML is a MIME container from a browser 'save page', not raw HTML."""
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from ingest import _html_to_text

        assert _html_to_text("<p>Hello</p><style>x{}</style>") == "Hello"

    def test_entities_are_unescaped(self):
        from ingest import _html_to_text

        assert "&" in _html_to_text("<p>A &amp; B</p>")

    def test_script_and_style_are_dropped(self):
        from ingest import _html_to_text

        out = _html_to_text("<style>p{color:red}</style><p>Body</p>")
        assert "color" not in out and "Body" in out
