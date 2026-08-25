"""Hybrid retrieval with version grouping.

Dense and lexical retrieval are fused with Reciprocal Rank Fusion. RRF is used
rather than a weighted score blend because cosine similarities and BM25 scores
are on incompatible scales, and normalising them introduces a tuning parameter
that would need a labelled set to fit. RRF only needs the rankings.

The part specific to this corpus is what happens next.

Three of the four documents are the same bill at different legislative stages,
so their text is near-identical. A query for "no tax on tips" returns the same
provision three times - from the House draft, the Senate substitute, and the
enacted law - at nearly indistinguishable scores. Left alone, a top-5 becomes
one provision repeated, and the remaining four relevant provisions never
surface.

The fix is to group rather than discard. Chunks describing the same provision
are collapsed into a single result carrying its variants, so:

  * top-k counts distinct provisions, not distinct documents;
  * the enacted text leads, because that is what "what does the law say" means;
  * the other versions stay attached, so a question about what changed between
    stages can still be answered, and an answer drawn from a draft can be
    labelled as a proposal rather than reported as law.

Section numbers cannot be the grouping key - the same provision is SEC. 70201 in
the enrolled bill and SEC. 110101 in the House draft. Section *headings* are
stable across versions, so they are the join key.
"""

from __future__ import annotations

import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from index import BM25_PATH, CHROMA_DIR, COLLECTION, EMBED_MODEL, tokenize

REPO_ROOT = Path(__file__).resolve().parent.parent

# Standard RRF constant. Large enough that the top few ranks of either retriever
# do not dominate outright, so a result both rankers like beats one that only a
# single ranker ranks first.
RRF_K = 60

# How deep each retriever goes before fusion. Deeper than the final k because
# near-duplicates collapse afterwards, and because a provision ranked 30th by
# one retriever and 2nd by the other is exactly what fusion should surface.
CANDIDATE_DEPTH = 60

# Enacted law leads a version group; drafts follow in legislative order.
STAGE_PRIORITY = {"enrolled": 0, "senate_substitute": 1, "house_passed": 2}

# The advocacy document is 59 chunks against 2,417 of statute, but it wins
# retrieval far out of proportion to its size because it is written in the
# language people ask questions in. "Does the bill eliminate tax on tips?"
# matches the CEA report's plain prose, while the provision that actually does
# it reads "Part VII of subchapter B of chapter 1 is amended by redesignating
# section 224 as section 225" - relevant, but lexically nothing like the query.
#
# Unfiltered, that put advocacy in four of the top five slots and pushed the
# enacted law to second. Capping its share keeps it reachable for questions it
# genuinely answers ("what does CEA project for wages?") without letting it
# crowd out the statute on questions about what the law says.
ADVOCACY_SHARE = 0.25


# A long section is split across several chunks, and retrieval scores each one
# separately. That means the chunk defining a term can win while the chunk
# stating the dollar limit loses, and the answer then reports - accurately, and
# uselessly - that the limit "isn't in the excerpts I have". Observed on SEC.
# 70201, which is 7 chunks: asking for the tips cap retrieved the definitional
# chunks and missed the $25,000.
#
# So once a section is retrieved at all, its remaining chunks are pulled in and
# the section is reassembled in document order. Retrieval still ranks by chunk;
# the unit handed to the model is the provision. The cap below bounds the worst
# case - the longest section in this corpus is well under it.
SECTION_EXPANSION_MAX_CHARS = 24000


@dataclass
class Result:
    chunk_id: str
    text: str
    score: float
    metadata: dict
    # Same provision in other bill versions, ordered by stage.
    variants: list[dict] = field(default_factory=list)
    # Chunks of this section that retrieval did not rank but that were pulled
    # in to complete it. Recorded so the expansion is visible rather than silent.
    expanded_from: list[str] = field(default_factory=list)

    @property
    def citation(self) -> str:
        m = self.metadata
        if m.get("section"):
            where = m["doc_id"]
            if m.get("title"):
                where += f" Title {m['title']}"
            return f"{where} SEC. {m['section']} (p. {m['page_start']})"
        return f"{m['doc_id']} p. {m['page_start']}"


class Retriever:
    def __init__(self) -> None:
        self.model = SentenceTransformer(EMBED_MODEL)
        self.collection = chromadb.PersistentClient(
            path=str(CHROMA_DIR)
        ).get_collection(COLLECTION)
        with BM25_PATH.open("rb") as fh:
            state = pickle.load(fh)
        self.bm25 = state["bm25"]
        self.bm25_ids = state["ids"]

    # -- individual retrievers -------------------------------------------------

    def _dense(self, query: str, depth: int, where: dict | None) -> list[str]:
        response = self.collection.query(
            query_embeddings=self.model.encode(
                [query], normalize_embeddings=True
            ).tolist(),
            n_results=depth,
            where=where or None,
        )
        return response["ids"][0]

    def _lexical(self, query: str, depth: int, allowed: set[str] | None) -> list[str]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: -scores[i])
        out = []
        for i in ranked:
            if scores[i] <= 0:
                break
            chunk_id = self.bm25_ids[i]
            if allowed is not None and chunk_id not in allowed:
                continue
            out.append(chunk_id)
            if len(out) >= depth:
                break
        return out

    # -- fusion ----------------------------------------------------------------

    @staticmethod
    def _fuse(rankings: list[list[str]]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for ranking in rankings:
            for rank, chunk_id in enumerate(ranking):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        return scores

    @staticmethod
    def _provision_key(meta: dict) -> str:
        """Key identifying the same provision across bill versions.

        Headings are stable across versions where section numbers are not.
        Documents without headings (the OCR'd report) fall back to their own
        chunk identity so they are never grouped with statutory text.
        """
        heading = (meta.get("section_heading") or "").strip().lower()
        if not heading:
            return f"{meta['doc_id']}:{meta.get('page_start')}"

        # Only documents that are versions of the SAME bill may be collapsed.
        # Heading text alone is not enough: "Short title" appears in every bill
        # ever written, and grouping two unrelated bills under it would present
        # one as a variant of the other. Documents with no version_group are
        # scoped to themselves and never merge.
        group = meta.get("version_group") or f"solo:{meta['doc_id']}"
        return f"{group}:" + re.sub(r"[^a-z0-9 ]", "", heading)

    def _complete_section(self, result: Result) -> None:
        """Reassemble a result's full section from all of its chunks."""
        meta = result.metadata
        if not meta.get("section"):
            return

        siblings = self.collection.get(
            where={
                "$and": [
                    {"doc_id": meta["doc_id"]},
                    {"section": meta["section"]},
                ]
            },
            include=["documents", "metadatas"],
        )
        if len(siblings["ids"]) <= 1:
            return

        # Chunk ids end in the part index, so ordering by it restores document
        # order. Overlap between adjacent windows is left in place: removing it
        # risks cutting a clause, and duplication costs only tokens.
        ordered = sorted(
            zip(siblings["ids"], siblings["documents"], siblings["metadatas"]),
            key=lambda row: int(row[0].rsplit(":", 1)[-1]),
        )

        parts, total, pulled = [], 0, []
        for chunk_id, document, _ in ordered:
            if total + len(document) > SECTION_EXPANSION_MAX_CHARS:
                break
            parts.append(document)
            total += len(document)
            if chunk_id != result.chunk_id:
                pulled.append(chunk_id)

        if len(parts) > 1:
            result.text = "\n".join(parts)
            result.expanded_from = pulled
            result.metadata = {
                **meta,
                "page_end": max(m["page_end"] for _, _, m in ordered),
                "page_start": min(m["page_start"] for _, _, m in ordered),
            }

    # -- public API ------------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 8,
        authority: str | None = None,
        jurisdiction: str | None = None,
        group_versions: bool = True,
        expand_sections: bool = True,
    ) -> list[Result]:
        """Retrieve the top-k provisions for a query.

        `authority` filters to "law", "proposal" or "advocacy". `group_versions`
        collapses the same provision across bill versions into one result; turn
        it off to compare versions side by side. `expand_sections` reassembles
        each result's full section from its chunks, so a provision is never
        answered from a fragment of itself.
        """
        if not query or not query.strip():
            return []

        clauses = []
        if authority:
            clauses.append({"authority": authority})
        if jurisdiction:
            clauses.append({"jurisdiction": jurisdiction})
        if not clauses:
            where = None
        elif len(clauses) == 1:
            where = clauses[0]
        else:
            where = {"$and": clauses}
        dense = self._dense(query, CANDIDATE_DEPTH, where)
        allowed = set(dense) if where else None
        lexical = self._lexical(query, CANDIDATE_DEPTH, allowed)

        fused = self._fuse([dense, lexical])
        if not fused:
            return []

        records = self.collection.get(
            ids=list(fused), include=["documents", "metadatas"]
        )
        by_id = {
            cid: (doc, meta)
            for cid, doc, meta in zip(
                records["ids"], records["documents"], records["metadatas"]
            )
        }

        ordered = sorted(fused, key=lambda cid: -fused[cid])
        if not group_versions:
            flat = [
                Result(cid, by_id[cid][0], fused[cid], by_id[cid][1])
                for cid in ordered[:k]
                if cid in by_id
            ][:k]
            if expand_sections:
                for result in flat:
                    self._complete_section(result)
            return flat

        # Collapse version duplicates, keeping enacted text as the representative.
        groups: dict[str, list[str]] = {}
        for chunk_id in ordered:
            if chunk_id not in by_id:
                continue
            groups.setdefault(self._provision_key(by_id[chunk_id][1]), []).append(
                chunk_id
            )

        # Reserve most of the top-k for statutory text. Advocacy is not dropped,
        # only capped - unless the caller explicitly asked for it.
        advocacy_budget = (
            k if authority == "advocacy" else max(1, int(k * ADVOCACY_SHARE))
        )

        results: list[Result] = []
        deferred: list[Result] = []
        for key in sorted(groups, key=lambda g: -fused[groups[g][0]]):
            members = groups[key]
            # One chunk per document, then enacted first.
            best_per_doc: dict[str, str] = {}
            for chunk_id in members:
                doc_id = by_id[chunk_id][1]["doc_id"]
                if doc_id not in best_per_doc:
                    best_per_doc[doc_id] = chunk_id

            ranked = sorted(
                best_per_doc.values(),
                key=lambda cid: (
                    STAGE_PRIORITY.get(by_id[cid][1].get("stage"), 9),
                    -fused[cid],
                ),
            )
            primary = ranked[0]
            # Variants carry their own chunk_id so a claim about another version
            # can cite that version directly. Without it the model attributes
            # such a claim to the primary chunk, producing a citation that
            # points at the wrong document.
            result = Result(
                chunk_id=primary,
                text=by_id[primary][0],
                score=fused[primary],
                metadata=by_id[primary][1],
                variants=[{**by_id[c][1], "chunk_id": c} for c in ranked[1:]],
            )

            if by_id[primary][1].get("authority") == "advocacy":
                if advocacy_budget <= 0:
                    deferred.append(result)
                    continue
                advocacy_budget -= 1

            results.append(result)
            if len(results) >= k:
                break

        # Backfill from what the cap held back, rather than returning short.
        if len(results) < k:
            results.extend(deferred[: k - len(results)])

        if expand_sections:
            for result in results:
                self._complete_section(result)

        return results


if __name__ == "__main__":
    import sys

    retriever = Retriever()
    question = " ".join(sys.argv[1:]) or "does the bill eliminate tax on tips?"
    for i, result in enumerate(retriever.search(question), 1):
        meta = result.metadata
        print(f"\n{i}. [{meta['authority']}] {result.citation}  ({result.score:.4f})")
        if meta.get("section_heading"):
            print(f"   {meta['section_heading']}")
        if result.variants:
            other = ", ".join(
                f"{v['doc_id']}:SEC.{v['section']}" for v in result.variants
            )
            print(f"   also in: {other}")
        print(f"   {result.text[:150].strip()}...")
