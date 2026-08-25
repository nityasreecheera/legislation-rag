"""Provision-level diff between bill versions.

Answers the question retrieval structurally cannot: which policies in a draft
did not survive into the enacted law. Top-k retrieval can never establish
absence - eight chunks out of 2,365 say nothing about the other 2,357 - so this
works over the whole corpus instead of a retrieved window.

Three signals are computed for every provision in the source version:

  Heading match. Provisions often keep their heading across versions, but not
  reliably enough to stand alone: heading matching by itself reports 246 of 351
  House provisions as missing from the enrolled bill, which is badly overstated.
  "MAGA ACCOUNTS" was not dropped, it became "Trump accounts"; "THRIFTY FOOD
  PLAN" became "RE-EVALUATION OF THRIFTY FOOD PLAN".

  Body-text similarity. A renamed provision usually keeps its operative text, so
  its nearest enrolled section by embedding similarity is still itself.

  Statutory fingerprint. What survives even a thorough rename is the law being
  amended: the House MAGA provision creates Internal Revenue Code section 530A,
  and so does enrolled SEC. 70204. References are compared as an IDF-weighted
  vector, so a shared "section 1400Z" counts heavily and a shared "section 1"
  counts for almost nothing.

WHAT THIS TOOL DELIBERATELY DOES NOT DO

It does not claim a provision was dropped. It was built to, and the attempt
failed in a way worth recording, because the failure is the interesting result.

Neither signal separates "renamed" from "dropped" cleanly:

  - Text similarity called MAGA Accounts dropped (0.788) when it survived.
  - Adding the statutory fingerprint fixed that class of error, but at any
    threshold low enough to catch MAGA Accounts (0.54) it also matched the
    section 899 "unfair foreign taxes" provision (0.62) - which really was
    dropped - to the base erosion minimum tax, a different policy that shares
    references incidentally.
  - Scoring by the single rarest shared reference was worse still: nearly every
    provision shares some code with some enrolled section, so the scores
    saturated and the matches became arbitrary.

Tuning past that point would have meant fitting thresholds to the four cases I
had already verified by hand, which would look accurate and generalise to
nothing. So the classifier was replaced with triage:

  enacted          heading matches an enrolled section - high confidence
  likely_renamed   heading differs but text or statutory fingerprint is a
                   strong match - high confidence, counterpart named
  no_counterpart   both signals find nothing close - the strongest evidence of
                   a drop this can offer, and still only evidence
  needs_review     everything else, ranked by how much text is at stake

`needs_review` is the honest home for the hard cases rather than a rounding
error. A human reading 80 ranked candidates with suggested counterparts is far
better off than one reading 1,116 pages, and far better off than trusting a
label that is wrong an unknown fraction of the time.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from index import EMBED_MODEL

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = REPO_ROOT / "data" / "chunks.jsonl"

# Calibrated against the corpus, not guessed. Sections that DO match by heading
# - so are known to be the same provision - have a median best-text-similarity
# of 0.923 (10th percentile 0.885); sections that do not have a median of 0.826.
#
# Both bounds are set conservatively, because the cost of the two errors is not
# symmetric. Calling a surviving provision "renamed" wrongly points a reader at
# the wrong section; calling a dropped one "no counterpart" wrongly tells them a
# policy is dead when it is law. Anything ambiguous goes to needs_review.
RENAMED_MIN = 0.93          # text similarity: confident same provision
FINGERPRINT_MIN = 0.90      # statutory refs: confident same provision
NO_COUNTERPART_TEXT = 0.75  # below this on BOTH signals, nothing close exists
NO_COUNTERPART_REF = 0.45

# Shared IDF mass at which the fingerprint is considered fully informative.
# Roughly one rare code, or a handful of moderately common ones.
IDF_SATURATION = 4.0

# "section 530A", "sections 1400Z-2", "section 6039K" - the law a provision
# amends. Trailing letters matter: 529 and 529A are different programmes.
STATUTORY_REF = re.compile(r"\b(?:section|sections)\s+(\d{1,4}[A-Z]{0,2})\b", re.I)

# Only the opening of a section is embedded. It carries the operative language,
# and the model truncates at 512 tokens regardless.
COMPARE_CHARS = 1500

TARGET = "hr1-enrolled"
SOURCES = {"house": "hr1-house-passed", "senate": "hr1-senate-substitute"}


@dataclass
class Verdict:
    section: str
    heading: str
    status: str  # enacted | likely_renamed | needs_review | no_counterpart
    similarity: float
    fingerprint: float
    counterpart_section: str | None
    counterpart_heading: str | None
    chars: int
    evidence: str  # which signal decided it


def fingerprint_matrix(source_texts: list[str], target_texts: list[str]) -> np.ndarray:
    """Cosine similarity over IDF-weighted statutory-reference vectors."""
    def refs(text: str) -> Counter:
        return Counter(m.group(1).upper() for m in STATUTORY_REF.finditer(text))

    source_refs = [refs(t) for t in source_texts]
    target_refs = [refs(t) for t in target_texts]

    # Document frequency over the target corpus - "section 1" appears
    # everywhere and must not carry weight; "section 1400Z" appears in one
    # policy area and should dominate a match.
    document_frequency: Counter = Counter()
    for counter in target_refs:
        document_frequency.update(counter.keys())
    total = len(target_refs) or 1
    idf = {
        ref: math.log(total / (1 + count)) + 1.0
        for ref, count in document_frequency.items()
    }

    vocabulary = sorted(idf)
    index = {ref: i for i, ref in enumerate(vocabulary)}

    def vectorise(counters: list[Counter]) -> np.ndarray:
        matrix = np.zeros((len(counters), len(vocabulary)), dtype=np.float32)
        for row, counter in enumerate(counters):
            for ref, count in counter.items():
                if ref in index:
                    matrix[row, index[ref]] = math.log1p(count) * idf[ref]
        return matrix

    raw_source, raw_target = vectorise(source_refs), vectorise(target_refs)

    def unit(matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.clip(norms, 1e-9, None)

    cosine = unit(raw_source) @ unit(raw_target).T

    # Cosine alone is direction only, so two provisions sharing exactly one
    # reference score 1.0 even when that reference is worthless - normalisation
    # cancels the IDF weight that was supposed to suppress it. Scale by how much
    # information the overlap actually carries: the IDF mass the two share.
    # A single rare code clears the bar; several common ones do not.
    shared_mass = np.minimum(raw_source[:, None, :], raw_target[None, :, :]).sum(axis=2)
    confidence = np.tanh(shared_mass / IDF_SATURATION)

    return cosine * confidence


def normalise(heading: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (heading or "").lower()).strip()


def load_sections() -> tuple[dict, dict, dict]:
    """Reassemble whole sections from chunks, keyed by (doc_id, section)."""
    text: dict[tuple[str, str], str] = defaultdict(str)
    heading: dict[tuple[str, str], str] = {}
    order: dict[tuple[str, str], int] = {}

    with CHUNKS_PATH.open() as fh:
        for line in fh:
            chunk = json.loads(line)
            if not (chunk["section"] and chunk["section_heading"]):
                continue
            key = (chunk["doc_id"], chunk["section"])
            text[key] += chunk["text"]
            heading[key] = chunk["section_heading"]
            order.setdefault(key, chunk["page_start"])
    return text, heading, order


def compare(source_doc: str) -> list[Verdict]:
    text, heading, _ = load_sections()
    source = [k for k in text if k[0] == source_doc]
    target = [k for k in text if k[0] == TARGET]
    if not source or not target:
        raise SystemExit(f"missing sections for {source_doc} or {TARGET}")

    model = SentenceTransformer(EMBED_MODEL)
    encode = lambda keys: model.encode(  # noqa: E731
        [text[k][:COMPARE_CHARS] for k in keys],
        normalize_embeddings=True,
        batch_size=64,
    )
    similarity = encode(source) @ encode(target).T
    fingerprint = fingerprint_matrix(
        [text[k] for k in source], [text[k] for k in target]
    )

    target_headings = {normalise(heading[k]): k for k in target}
    verdicts: list[Verdict] = []

    for i, key in enumerate(source):
        best = int(similarity[i].argmax())
        score = float(similarity[i][best])
        fp_best = int(fingerprint[i].argmax())
        fp_score = float(fingerprint[i][fp_best])
        exact = target_headings.get(normalise(heading[key]))

        if exact:
            status, counterpart, evidence = "enacted", exact, "heading"
        elif score >= RENAMED_MIN:
            status, counterpart, evidence = "likely_renamed", target[best], "text"
        elif fp_score >= FINGERPRINT_MIN:
            # Renamed hard enough that the text embedding lost it, but still
            # amending the same law - this is what catches Opportunity Zones.
            status, counterpart, evidence = (
                "likely_renamed", target[fp_best], "statute-ref"
            )
        elif score <= NO_COUNTERPART_TEXT and fp_score <= NO_COUNTERPART_REF:
            status, counterpart, evidence = "no_counterpart", target[best], "neither"
        else:
            # The honest home for the hard cases. Best candidate still reported.
            pick = target[best] if score >= fp_score else target[fp_best]
            status, counterpart, evidence = "needs_review", pick, "weak"

        verdicts.append(
            Verdict(
                section=key[1],
                heading=heading[key],
                status=status,
                similarity=round(score, 3),
                fingerprint=round(fp_score, 3),
                counterpart_section=counterpart[1] if counterpart else None,
                counterpart_heading=heading[counterpart] if counterpart else None,
                chars=len(text[key]),
                evidence=evidence,
            )
        )

    return verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from", dest="source", default="house", choices=SOURCES)
    parser.add_argument(
        "--status",
        choices=["enacted", "likely_renamed", "needs_review", "no_counterpart"],
    )
    parser.add_argument("--top", type=int, default=15, help="rows to show")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    source_doc = SOURCES[args.source]
    verdicts = compare(source_doc)

    if args.json:
        print(json.dumps([asdict(v) for v in verdicts], indent=2))
        return

    counts: dict[str, int] = defaultdict(int)
    volume: dict[str, int] = defaultdict(int)
    for verdict in verdicts:
        counts[verdict.status] += 1
        volume[verdict.status] += verdict.chars
    total_chars = sum(volume.values()) or 1

    print(f"\n{source_doc}  ->  {TARGET}\n{'=' * 72}")
    print(f"{'status':12s} {'sections':>9s} {'text':>9s}  share of draft")
    print("-" * 72)
    for status in ("enacted", "likely_renamed", "needs_review", "no_counterpart"):
        print(
            f"{status:12s} {counts[status]:>9d} {volume[status]:>8,d}c "
            f"{volume[status] / total_chars:>13.0%}"
        )
    print("-" * 72)
    print(f"{'total':12s} {len(verdicts):>9d} {total_chars:>8,d}c")

    shown = [v for v in verdicts if not args.status or v.status == args.status]
    shown.sort(key=lambda v: -v.chars)
    label = args.status or "all"
    print(f"\nLargest '{label}' provisions:\n" + "-" * 72)
    for verdict in shown[: args.top]:
        print(f"SEC. {verdict.section:<8s} {verdict.chars:>7,d}c  "
              f"{verdict.status:<9s} sim={verdict.similarity:.3f} "
              f"ref={verdict.fingerprint:.2f} ({verdict.evidence})")
        print(f"    {verdict.heading[:66]}")
        if verdict.counterpart_heading and verdict.status != "enacted":
            print(f"    -> {TARGET} SEC. {verdict.counterpart_section}: "
                  f"{verdict.counterpart_heading[:52]}")

    if not args.status:
        print(
            "\nThis is triage, not a verdict. No signal tested separates "
            "'renamed' from\n'dropped' reliably (see the module docstring), so "
            "ambiguous provisions go to\nneeds_review with their best candidate "
            "rather than getting a confident label."
        )


if __name__ == "__main__":
    main()
