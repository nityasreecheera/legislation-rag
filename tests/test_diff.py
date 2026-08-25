"""Tests for the version-diff triage tool.

The property that matters is not accuracy of the labels - no signal tested
separates renamed from dropped reliably - but that the confident classes stay
confident. A provision that survived must never be labelled `no_counterpart`,
because that would tell a reader a policy is dead when it is law.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from diff import (  # noqa: E402
    STATUTORY_REF,
    Verdict,
    fingerprint_matrix,
    normalise,
)


class TestStatutoryReferences:
    def test_extracts_code_sections(self):
        text = "Section 530A of the Internal Revenue Code and sections 1400Z-2"
        assert set(STATUTORY_REF.findall(text)) == {"530A", "1400Z"}

    def test_trailing_letters_are_significant(self):
        """529 and 529A are different programmes."""
        found = STATUTORY_REF.findall("section 529 and section 529A")
        assert found == ["529", "529A"]

    def test_ignores_prose_numbers(self):
        assert not STATUTORY_REF.findall("within 30 days of the 2025 deadline")


class TestFingerprint:
    def test_shared_rare_reference_scores_high(self):
        source = ["amends section 1400Z and section 1400Z-2 extensively"]
        target = [
            "modifies section 1400Z rules for opportunity zones",
            "unrelated provision concerning section 1 generally",
        ]
        scores = fingerprint_matrix(source, target)[0]
        assert scores[0] > scores[1]

    def test_shared_common_reference_scores_low(self):
        """A shared 'section 1' is not evidence - IDF must suppress it."""
        target = [f"provision citing section 1 number {i}" for i in range(20)]
        scores = fingerprint_matrix(["citing section 1 only"], target)[0]
        assert scores.max() < 0.99

    def test_no_shared_references_scores_zero(self):
        scores = fingerprint_matrix(["section 9999"], ["section 1111"])[0]
        assert scores[0] == pytest.approx(0.0, abs=1e-6)

    def test_empty_reference_set_does_not_divide_by_zero(self):
        scores = fingerprint_matrix(["no citations here"], ["section 42"])
        assert np.isfinite(scores).all()


class TestHeadingNormalisation:
    @pytest.mark.parametrize(
        "a,b",
        [
            ("NO TAX ON TIPS.", "No Tax on Tips"),
            ("CELEBRATING AMERICA'S 250TH ANNIVERSARY.", "celebrating americas 250th anniversary"),
        ],
    )
    def test_equivalent_headings_normalise_alike(self, a, b):
        assert normalise(a) == normalise(b)

    def test_distinct_headings_stay_distinct(self):
        assert normalise("THRIFTY FOOD PLAN.") != normalise(
            "RE-EVALUATION OF THRIFTY FOOD PLAN."
        )

    def test_none_is_handled(self):
        assert normalise(None) == ""


class TestTriageOverCorpus:
    @pytest.fixture(scope="class")
    def verdicts(self):
        if not (Path(__file__).resolve().parent.parent / "data" / "chunks.jsonl").exists():
            pytest.skip("corpus not built")
        from diff import compare

        return {v.section: v for v in compare("hr1-house-passed")}

    def test_every_provision_is_classified(self, verdicts):
        allowed = {"enacted", "likely_renamed", "needs_review", "no_counterpart"}
        assert all(v.status in allowed for v in verdicts.values())

    def test_surviving_provisions_are_never_called_missing(self, verdicts):
        """Hand-verified survivors. Labelling any of these `no_counterpart`
        would tell a reader a policy is dead when it is law.

        110115 MAGA Accounts   -> enacted as "Trump accounts"
        111102 Opportunity Zones -> enacted as SEC. 70421
        100009 Kennedy Center  -> present in the enrolled bill
        """
        for section in ("110115", "111102", "100009"):
            if section in verdicts:
                assert verdicts[section].status != "no_counterpart", section

    def test_confident_labels_name_a_counterpart(self, verdicts):
        for verdict in verdicts.values():
            if verdict.status in {"enacted", "likely_renamed"}:
                assert verdict.counterpart_section, verdict.section

    def test_scores_are_in_range(self, verdicts):
        for verdict in verdicts.values():
            assert -0.01 <= verdict.similarity <= 1.01
            assert -0.01 <= verdict.fingerprint <= 1.01
