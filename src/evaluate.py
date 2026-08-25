"""Run the evaluation set and score it.

Four things are scored, all mechanically checkable:

  grounded    No citation points at a chunk that was not retrieved. This is the
              hallucinated-citation check, and it is pass/fail per question.

  citations   Did the answer cite the sections the question is actually about?
              Measured as recall over the expected sections, because an answer
              may legitimately cite more than the minimum.

  abstention  For questions with no answer in the corpus, the answer must say
              so. Scored separately because a system that abstains on everything
              would otherwise look perfect on groundedness.

              This was originally scored as "cited nothing", which was wrong.
              The best abstention this pipeline produced cited six chunks - to
              show what it had searched, and to rule out a near-miss (section
              280C, one character from the 280E the question asked about). That
              is more useful than a bare refusal, and the metric was marking it
              a failure. Abstention is now judged on whether the answer declines
              in words, not on whether it cites; citing nothing is recorded
              alongside it as information rather than as the test.

  phrasing    Required substrings must appear and forbidden ones must not. This
              is where authority handling is caught: "project" must appear when
              the source is advocacy, "the law provides" must not appear when
              the source is a draft.

Phrase checks are crude - they catch the blatant failures, not subtle ones. The
write-up says so rather than implying the score is a quality measure.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml

from answer import Pipeline

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_SET = REPO_ROOT / "eval" / "eval_set.yaml"
RESULTS_DIR = REPO_ROOT / "eval" / "results"

# Phrases that mark an explicit decline. Crude by design - they catch a stated
# refusal, not a subtly evasive answer. A question expecting abstention passes
# when one of these appears; whether it also cited chunks is recorded but not
# scored, because listing what was searched makes a refusal more useful.
ABSTENTION_MARKERS = (
    "don't find",
    "do not find",
    "not in these",
    "nothing here",
    "no excerpt",
    "not among these",
    "isn't in these",
    "would need",
    "not addressed in",
    "does not appear in these",
)


def load_eval_set(path: Path = EVAL_SET) -> list[dict]:
    with path.open() as fh:
        return yaml.safe_load(fh)["questions"]


def score_one(case: dict, answer) -> dict:
    """Score a single answer against its expectations."""
    cited = set(answer.cited_ids)
    cited_pairs = {
        (result.metadata["doc_id"], result.metadata.get("section") or None)
        for result in answer.results
        if result.chunk_id in cited
    }
    # Variants are citable too, so include any that were cited.
    for result in answer.results:
        for variant in result.variants:
            if variant.get("chunk_id") in cited:
                cited_pairs.add((variant["doc_id"], variant.get("section")))

    expected = [
        (item["doc_id"], item.get("section")) for item in case.get("expect_sections", [])
    ]
    matched = [pair for pair in expected if pair in cited_pairs]

    lowered = answer.text.lower()
    missing_phrases = [
        phrase for phrase in case.get("expect_phrases", [])
        if phrase.lower() not in lowered
    ]
    present_forbidden = [
        phrase for phrase in case.get("forbid_phrases", [])
        if phrase.lower() in lowered
    ]

    wants_abstain = bool(case.get("expect_abstain"))
    declined = any(marker in lowered for marker in ABSTENTION_MARKERS)
    abstention_ok = declined if wants_abstain else not answer.abstained

    passed = (
        answer.grounded
        and abstention_ok
        and not missing_phrases
        and not present_forbidden
        and (not expected or len(matched) == len(expected))
    )

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "passed": passed,
        "grounded": answer.grounded,
        "unverified": answer.unverified,
        "abstention_ok": abstention_ok,
        "declined_in_words": declined,
        "cited_nothing": answer.abstained,
        "expected_sections": [f"{d}:{s}" for d, s in expected],
        "matched_sections": [f"{d}:{s}" for d, s in matched],
        "citation_recall": (len(matched) / len(expected)) if expected else None,
        "missing_phrases": missing_phrases,
        "forbidden_present": present_forbidden,
        "answer": answer.text,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run a single question by id")
    parser.add_argument("-k", type=int, default=8, help="chunks retrieved per question")
    args = parser.parse_args()

    cases = load_eval_set()
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]
        if not cases:
            raise SystemExit(f"no question with id {args.only!r}")

    pipeline = Pipeline()
    scored = []
    for index, case in enumerate(cases, 1):
        print(f"[{index}/{len(cases)}] {case['id']}", flush=True)
        scored.append(score_one(case, pipeline.ask(case["question"], k=args.k)))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (RESULTS_DIR / f"eval-{stamp}.json").write_text(json.dumps(scored, indent=2))

    print("\n" + "=" * 76)
    print(f"{'id':28s} {'cat':22s} {'grnd':5s} {'cite':6s} pass")
    print("-" * 76)
    for row in scored:
        recall = row["citation_recall"]
        print(
            f"{row['id']:28s} {row['category']:22s} "
            f"{'ok' if row['grounded'] else 'FAIL':5s} "
            f"{('-' if recall is None else f'{recall:.0%}'):6s} "
            f"{'PASS' if row['passed'] else 'FAIL'}"
        )

    passed = sum(r["passed"] for r in scored)
    grounded = sum(r["grounded"] for r in scored)
    recalls = [r["citation_recall"] for r in scored if r["citation_recall"] is not None]
    print("-" * 76)
    print(f"passed        {passed}/{len(scored)}")
    print(f"grounded      {grounded}/{len(scored)}  (no hallucinated citations)")
    if recalls:
        print(f"citation recall {sum(recalls) / len(recalls):.0%}  (mean over {len(recalls)})")
    print(f"\nresults -> eval/results/eval-{stamp}.json")

    for row in scored:
        if not row["passed"]:
            reasons = []
            if not row["grounded"]:
                reasons.append(f"unverified={row['unverified']}")
            if not row["abstention_ok"]:
                reasons.append("abstention mismatch")
            missed = set(row["expected_sections"]) - set(row["matched_sections"])
            if missed:
                reasons.append(f"missed {sorted(missed)}")
            if row["missing_phrases"]:
                reasons.append(f"missing {row['missing_phrases']}")
            if row["forbidden_present"]:
                reasons.append(f"forbidden {row['forbidden_present']}")
            print(f"\nFAIL {row['id']}: {'; '.join(reasons)}")


if __name__ == "__main__":
    main()
