"""Tests for grounding: citation verification, context framing, rendering.

None of these call the API. The generation step is one request; what is worth
testing is everything around it - whether an invented citation is caught,
whether the authority labels actually reach the model, and whether an answer
with no sources is recognised as an abstention rather than reported as fact.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from answer import (  # noqa: E402
    Answer,
    format_context,
    render,
    verify_citations,
)
from retrieve import Result  # noqa: E402


def make_result(chunk_id="hr1-enrolled:70201:0", **overrides):
    metadata = {
        "doc_id": "hr1-enrolled",
        "authority": "law",
        "stage": "enrolled",
        "doc_type": "statute",
        "title": "VII",
        "section": "70201",
        "section_heading": "NO TAX ON TIPS.",
        "page_start": 99,
        "page_end": 103,
        "extraction": "text",
        "has_figure": False,
    }
    metadata.update(overrides)
    return Result(
        chunk_id=chunk_id,
        text="SEC. 70201. NO TAX ON TIPS.",
        score=0.03,
        metadata=metadata,
    )


def make_variant(**overrides):
    """The same provision as it appears in another bill version."""
    variant = {
        "chunk_id": "hr1-house-passed:110101:0",
        "doc_id": "hr1-house-passed",
        "authority": "proposal",
        "stage": "house_passed",
        "title": "XI",
        "section": "110101",
        "section_heading": "NO TAX ON TIPS.",
        "page_start": 750,
    }
    variant.update(overrides)
    return variant


class TestCitationVerification:
    def test_valid_citation_is_accepted(self):
        results = [make_result()]
        cited, unverified = verify_citations(
            "Tips are deductible [hr1-enrolled:70201:0].", results
        )
        assert cited == ["hr1-enrolled:70201:0"]
        assert unverified == []

    def test_invented_citation_is_caught(self):
        """The failure this whole layer exists to catch: a plausible-looking id
        for a chunk that was never retrieved."""
        results = [make_result()]
        cited, unverified = verify_citations(
            "The bill does X [hr1-enrolled:99999:0].", results
        )
        assert cited == []
        assert unverified == ["hr1-enrolled:99999:0"]

    def test_real_id_not_in_context_is_still_unverified(self):
        """An id that exists in the corpus but was not among the retrieved
        chunks cannot have supported the claim."""
        cited, unverified = verify_citations(
            "Claim [hr1-senate-substitute:70201:0].", [make_result()]
        )
        assert unverified == ["hr1-senate-substitute:70201:0"]

    def test_variant_id_counts_as_verified(self):
        """A version variant was shown in the context, so citing it is correct -
        and is what the model should do instead of attaching a claim about
        another document to the primary chunk."""
        result = make_result()
        result.variants = [make_variant()]
        cited, unverified = verify_citations(
            "The House draft numbered it SEC. 110101 [hr1-house-passed:110101:0].",
            [result],
        )
        assert cited == ["hr1-house-passed:110101:0"]
        assert unverified == []

    def test_mixed_citations_are_separated(self):
        results = [make_result(), make_result("cea-report:p2:0")]
        cited, unverified = verify_citations(
            "A [hr1-enrolled:70201:0] and B [cea-report:p2:0] and C [made:up:1].",
            results,
        )
        assert set(cited) == {"hr1-enrolled:70201:0", "cea-report:p2:0"}
        assert unverified == ["made:up:1"]

    def test_repeated_citation_is_reported_once(self):
        results = [make_result()]
        cited, _ = verify_citations(
            "A [hr1-enrolled:70201:0]. B [hr1-enrolled:70201:0].", results
        )
        assert cited == ["hr1-enrolled:70201:0"]

    def test_uncited_answer_yields_nothing(self):
        cited, unverified = verify_citations("The bill does many things.", [make_result()])
        assert cited == [] and unverified == []


class TestContextFraming:
    def test_authority_label_reaches_the_model(self):
        """If the authority label is missing from the prompt, the model cannot
        distinguish enacted law from a dropped draft provision."""
        assert "authority=law" in format_context([make_result()])

    def test_advocacy_is_labelled(self):
        context = format_context(
            [make_result("cea-report:p2:0", authority="advocacy", section=None,
                         section_heading=None, doc_id="cea-report", stage=None)]
        )
        assert "authority=advocacy" in context

    def test_ocr_provenance_is_disclosed(self):
        context = format_context(
            [make_result("cea-report:p6:0", extraction="ocr", section=None,
                         section_heading=None, doc_id="cea-report", stage=None)]
        )
        assert "OCR" in context and "charts were not extracted" in context

    def test_version_variants_are_surfaced(self):
        result = make_result()
        result.variants = [make_variant()]
        context = format_context([result])
        assert "SAME PROVISION IN OTHER VERSIONS" in context
        assert "hr1-house-passed SEC. 110101" in context

    def test_variants_are_shown_with_their_own_chunk_id(self):
        """A claim about another version must be able to cite that version.

        Without a citable id the model attributes such claims to the primary
        chunk, producing a citation that points at the wrong document - an
        answer stating what the Senate draft says while citing the enrolled
        bill.
        """
        result = make_result()
        result.variants = [make_variant()]
        context = format_context([result])
        assert "[hr1-house-passed:110101:0]" in context
        assert "authority=proposal" in context

    def test_section_and_page_are_present_for_citation(self):
        context = format_context([make_result()])
        assert "SEC. 70201" in context and "p. 99" in context


class TestRendering:
    def test_chunk_ids_expand_to_readable_citations(self):
        answer = Answer(
            question="q",
            text="Tips are deductible [hr1-enrolled:70201:0].",
            results=[make_result()],
            cited_ids=["hr1-enrolled:70201:0"],
        )
        out = render(answer)
        assert "hr1-enrolled Title VII SEC. 70201, p. 99" in out
        assert "hr1-enrolled:70201:0" not in out.split("Sources:")[0]

    def test_unverified_citation_is_flagged_to_the_reader(self):
        answer = Answer(
            question="q",
            text="Claim [bogus:1:0].",
            results=[make_result()],
            unverified=["bogus:1:0"],
        )
        out = render(answer)
        assert "UNVERIFIED" in out and "WARNING" in out

    def test_abstention_is_marked(self):
        answer = Answer(
            question="q",
            text="I don't find that in these documents.",
            results=[make_result()],
        )
        assert "abstention" in render(answer)

    def test_refusal_is_not_treated_as_abstention(self):
        answer = Answer(
            question="q", text="declined", results=[], refused=True
        )
        assert "abstention" not in render(answer)


class TestAnswerProperties:
    def test_grounded_requires_all_citations_resolve(self):
        assert Answer("q", "t", [], cited_ids=["a:1:0"]).grounded
        assert not Answer("q", "t", [], unverified=["b:2:0"]).grounded

    @pytest.mark.parametrize(
        "kwargs,expected",
        [
            ({}, True),
            ({"cited_ids": ["a:1:0"]}, False),
            ({"refused": True}, False),
        ],
    )
    def test_abstention_detection(self, kwargs, expected):
        assert Answer("q", "t", [], **kwargs).abstained is expected


class TestEmptyInput:
    """Adversarial input required by the brief."""

    @pytest.mark.parametrize("question", ["", "   ", "\n\t"])
    def test_blank_question_short_circuits(self, question, monkeypatch):
        import answer as answer_module

        class FailingClient:
            def __getattr__(self, name):
                raise AssertionError("the API must not be called for a blank query")

        pipeline = object.__new__(answer_module.Pipeline)
        pipeline.retriever = None
        pipeline.client = FailingClient()

        result = answer_module.Pipeline.ask(pipeline, question)
        assert result.results == []
        assert "provide a question" in result.text.lower()
