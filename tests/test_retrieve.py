"""Tests for section expansion.

Regression: a long section is split across chunks and retrieval scores each
separately, so the chunk defining a term could win while the chunk holding the
dollar limit lost. The answer then correctly reported that the limit "isn't in
the excerpts" - a true statement about a broken retrieval.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


@pytest.fixture(scope="module")
def retriever():
    chroma = Path(__file__).resolve().parent.parent / "data" / "chroma"
    if not chroma.exists():
        pytest.skip("index not built; run src/index.py")
    from retrieve import Retriever

    return Retriever()


def test_section_is_reassembled_from_all_chunks(retriever):
    """SEC. 70201 is 7 chunks; the $25,000 cap is not in the top-ranked one."""
    results = retriever.search("What is the cap on the tips deduction?", k=4)
    section = next(
        r for r in results
        if r.metadata.get("section") == "70201"
        and r.metadata["doc_id"] == "hr1-enrolled"
    )
    assert section.expanded_from, "expected sibling chunks to be pulled in"
    assert "25,000" in section.text


def test_expansion_can_be_disabled(retriever):
    results = retriever.search(
        "What is the cap on the tips deduction?", k=4, expand_sections=False
    )
    assert all(not r.expanded_from for r in results)


def test_expansion_respects_the_size_cap(retriever):
    from retrieve import SECTION_EXPANSION_MAX_CHARS

    for result in retriever.search("appropriations for border security", k=6):
        assert len(result.text) <= SECTION_EXPANSION_MAX_CHARS


def test_page_range_covers_the_whole_section(retriever):
    for result in retriever.search("tips deduction limitation", k=4):
        if result.expanded_from:
            assert result.metadata["page_start"] <= result.metadata["page_end"]


def test_pageless_documents_are_not_expanded(retriever):
    """The OCR'd report has no sections, so there is nothing to reassemble."""
    results = retriever.search("what does the CEA project for GDP?", k=8)
    for result in results:
        if result.metadata["doc_id"] == "cea-report":
            assert not result.expanded_from
