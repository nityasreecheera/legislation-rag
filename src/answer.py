"""Grounded answer generation with citation verification.

The model is required to cite a chunk id for every factual claim. Those ids are
then checked against what was actually retrieved: an id that does not exist, or
that was never in the context window, is reported rather than rendered. This is
cheap and it catches the specific failure that matters here - a fluent answer
carrying a citation that does not support it.

The prompt's main job is not accuracy in the usual sense. Every document in this
corpus describes the same bill, but only one of them *is* the law:

  * `law`      - the enrolled text. What the statute actually says today.
  * `proposal` - a House or Senate draft. May have been amended or dropped
                 entirely; 263 provisions in this corpus exist in only one
                 version. Reporting one as current law is the worst error the
                 system can make, and the most natural one.
  * `advocacy` - the CEA report. Economic projections written by the
                 administration promoting its own bill. Frequently the best
                 lexical match for a question, and almost never the answer to
                 "what does the law say".

So answers must attribute by authority, not merely cite.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from retrieve import Result, Retriever

# Credentials come from .env (gitignored) or the ambient environment. Nothing
# is ever read from a committed file - see .env.example for the expected shape.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

# Server-side fallback: this corpus is politically charged (immigration
# enforcement, tax policy), so a policy decline is a realistic failure mode for
# a legitimate question. On a decline the API re-runs the request on a fallback
# model within the same call rather than returning nothing.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

CITATION = re.compile(r"\[([a-z0-9\-]+:[^\]\s]+)\]")

SYSTEM = """\
You answer questions about legislation using only the excerpts provided. The \
corpus is H.R. 1 (the federal "One Big Beautiful Bill Act") in three versions, \
a Council of Economic Advisers report about it, and three Arizona state bills. \
You have no other source. Do not use prior knowledge about these bills or about \
US law.

CITATIONS
Every factual claim must be followed by the chunk id it came from, in square \
brackets: [hr1-enrolled:70201:0]. Cite the id exactly as given. Never invent an \
id. If two excerpts support a claim, cite both.

AUTHORITY - this matters more than anything else here
Each excerpt is labelled with an authority level:

  law       The enrolled bill. This is what the statute actually says. Only \
excerpts labelled `law` may be described as what the law does, requires or \
provides.

  proposal  A House or Senate draft. These provisions may have been changed or \
dropped before enactment. Never state a `proposal` excerpt as current law. Say \
"the House version proposed..." or "an earlier draft would have...". If a \
question asks what the law says and you only have `proposal` excerpts, say the \
enacted text was not retrieved.

  advocacy  The Council of Economic Advisers report - the administration \
arguing for its own bill. Its figures are projections and political claims, not \
law and not neutral analysis. Never present them as what the bill does. \
Attribute them: "the CEA projects..." and note it is an executive-branch body \
advocating for the bill.

JURISDICTION
The corpus spans two jurisdictions, and they must never be mixed. Excerpts are \
labelled `jurisdiction=federal` (H.R. 1 and the CEA report) or \
`jurisdiction=arizona` (state bills, all engrossed - passed one chamber, not \
enacted). A question about federal law cannot be answered from an Arizona bill, \
and vice versa. If the excerpts are from the wrong jurisdiction for the \
question, say so rather than answering from them. Always name the jurisdiction \
when citing a state bill.

VERSIONS
The same provision often appears in several versions under different section \
numbers - "no tax on tips" is SEC. 70201 in the enrolled bill and SEC. 110101 \
in the House draft. A section number alone is ambiguous, so always name the \
document alongside it. Where versions differ, say so explicitly rather than \
blending them into one answer.

Some excerpts list SAME PROVISION IN OTHER VERSIONS, giving a chunk id for that \
provision in another document. When you say something about one of those other \
versions, cite its own id - not the id of the excerpt you are reading. Citing \
the enrolled bill for a statement about the House draft points the reader at \
the wrong document. Note that only the identity and location of those variants \
is given to you, not their text: you can say where the provision appears, but \
not what it says, unless its text is also among the excerpts.

WHEN THE EXCERPTS DO NOT ANSWER THE QUESTION
Say so plainly, and say what you would need. Do not answer from general \
knowledge, and do not stretch a loosely related excerpt into an answer. A \
question about state law, or about a topic this bill does not cover, has no \
answer in these documents. "I don't find that in these documents" is a correct \
and useful response.

Be concise. Lead with the answer."""


# A follow-up like "what about overtime?" is meaningless to a retriever on its
# own - it has no content words to match. Before retrieving, a follow-up is
# rewritten into a standalone question using the conversation so far. This runs
# at low effort with a small token budget: it is a rephrasing task, not a
# reasoning one.
REWRITE_SYSTEM = """\
Rewrite the user's latest question into a standalone search query, resolving \
pronouns and ellipsis from the conversation. Keep the user's terminology - \
especially section numbers, document names and legal terms. If the question is \
already self-contained, return it unchanged. Return only the rewritten query, \
with no preamble."""

# How many prior turns to carry. Legislative answers are long, so the window is
# deliberately short - enough for follow-ups, not enough to crowd out excerpts.
HISTORY_TURNS = 4


@dataclass
class Turn:
    question: str
    answer: str


@dataclass
class Answer:
    question: str
    text: str
    results: list[Result]
    retrieval_query: str = ""
    cited_ids: list[str] = field(default_factory=list)
    unverified: list[str] = field(default_factory=list)
    refused: bool = False

    @property
    def grounded(self) -> bool:
        """True when every citation resolves to a retrieved chunk."""
        return not self.unverified

    @property
    def abstained(self) -> bool:
        return not self.cited_ids and not self.refused


def format_context(results: list[Result]) -> str:
    """Render retrieved chunks for the prompt, authority label first."""
    blocks = []
    for result in results:
        meta = result.metadata
        header = (
            f"[{result.chunk_id}] authority={meta['authority']}"
            f" jurisdiction={meta.get('jurisdiction', 'federal')}"
        )
        if meta.get("stage"):
            header += f" stage={meta['stage']}"
        if meta.get("section"):
            where = f" | {meta['doc_id']}"
            if meta.get("title"):
                where += f" Title {meta['title']}"
            header += f"{where} SEC. {meta['section']}"
            if meta.get("section_heading"):
                header += f" - {meta['section_heading']}"
        else:
            header += f" | {meta['doc_id']}"
        header += f" (p. {meta['page_start']})"

        if result.variants:
            same = "; ".join(
                f"[{v['chunk_id']}] {v['doc_id']} SEC. {v['section']}"
                f" (authority={v['authority']}, p. {v['page_start']})"
                for v in result.variants
            )
            header += f"\n  SAME PROVISION IN OTHER VERSIONS: {same}"
        if meta.get("extraction") == "ocr":
            header += "\n  NOTE: OCR'd from an image; charts were not extracted."

        blocks.append(f"{header}\n{result.text}")

    return "\n\n---\n\n".join(blocks)


def cited_ids_in_context(results: list[Result]) -> set[str]:
    """Every id the model was shown - primaries plus their version variants.

    Variants are citable because their identity and provenance appear in the
    context, even though their full text does not. A claim like "the same
    provision is SEC. 110101 in the House draft" is supported by what was
    shown, and should cite that document rather than the primary chunk.
    """
    ids = {r.chunk_id for r in results}
    for result in results:
        ids.update(v["chunk_id"] for v in result.variants if v.get("chunk_id"))
    return ids


def verify_citations(text: str, results: list[Result]) -> tuple[list[str], list[str]]:
    """Split cited ids into those present in the context and those invented."""
    available = cited_ids_in_context(results)
    cited = list(dict.fromkeys(CITATION.findall(text)))
    return [c for c in cited if c in available], [
        c for c in cited if c not in available
    ]


class MissingCredentials(RuntimeError):
    """Raised at construction rather than at the first request.

    Without this the SDK fails deep inside the call with "Could not resolve
    authentication method", but only *after* the embedding model has loaded and
    retrieval has run - so the first thing anyone without a key sees is a
    traceback several seconds into what looked like a working system.
    """


CREDENTIAL_HELP = """\
No Anthropic API key found.

  1. Get a key:  https://console.anthropic.com/settings/keys
  2. Save it:    cp .env.example .env   and paste the key into .env

Retrieval works without a key - only answer generation needs one:

  .venv/bin/python src/retrieve.py "your question"    # ranked chunks
  .venv/bin/python src/diff.py --from house           # version comparison"""


class Pipeline:
    def __init__(self, retriever: Retriever | None = None) -> None:
        if not (os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
            raise MissingCredentials(CREDENTIAL_HELP)
        self.retriever = retriever or Retriever()
        self.client = anthropic.Anthropic()

    def rewrite_query(self, question: str, history: list[Turn]) -> str:
        """Resolve a follow-up into a standalone retrieval query."""
        if not history:
            return question

        transcript = "\n".join(
            f"Q: {turn.question}\nA: {turn.answer[:400]}"
            for turn in history[-HISTORY_TURNS:]
        )
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=200,
            system=REWRITE_SYSTEM,
            output_config={"effort": "low"},
            messages=[
                {
                    "role": "user",
                    "content": f"Conversation:\n{transcript}\n\nLatest: {question}",
                }
            ],
        )
        rewritten = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        return rewritten or question

    def ask(
        self,
        question: str,
        k: int = 8,
        history: list[Turn] | None = None,
        authority: str | None = None,
        jurisdiction: str | None = None,
    ) -> Answer:
        if not question or not question.strip():
            return Answer(
                question=question,
                text="Please provide a question.",
                results=[],
            )

        history = history or []
        search_query = self.rewrite_query(question.strip(), history)
        results = self.retriever.search(
            search_query, k=k, authority=authority, jurisdiction=jurisdiction
        )
        if not results:
            return Answer(
                question=question,
                text="Nothing in these documents matches that question.",
                results=[],
                retrieval_query=search_query,
            )

        prompt = (
            f"Excerpts:\n\n{format_context(results)}\n\n"
            f"---\n\nQuestion: {question.strip()}"
        )

        # Prior turns are replayed as conversation so follow-ups have context.
        # Only this turn's excerpts are attached: replaying old excerpts would
        # grow the context without bound and let a stale chunk be cited as
        # though it were retrieved for the current question.
        messages: list[dict] = []
        for turn in history[-HISTORY_TURNS:]:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant", "content": turn.answer})
        messages.append({"role": "user", "content": prompt})

        response = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM,
            messages=messages,
            thinking={"type": "adaptive"},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            return Answer(
                question=question,
                text=f"The request was declined by a safety classifier ({category}).",
                results=results,
                refused=True,
                retrieval_query=search_query,
            )

        text = "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        cited, unverified = verify_citations(text, results)

        return Answer(
            question=question,
            text=text,
            results=results,
            cited_ids=cited,
            unverified=unverified,
            retrieval_query=search_query,
        )


def render(answer: Answer) -> str:
    """Format an answer for the CLI, expanding chunk ids into readable cites."""
    by_id = {r.chunk_id: r.metadata for r in answer.results}
    for result in answer.results:
        for variant in result.variants:
            if variant.get("chunk_id"):
                by_id.setdefault(variant["chunk_id"], variant)

    def expand(match: re.Match) -> str:
        meta = by_id.get(match.group(1))
        if not meta:
            return f"[UNVERIFIED: {match.group(1)}]"
        if meta.get("section"):
            where = meta["doc_id"]
            if meta.get("title"):
                where += f" Title {meta['title']}"
            return f"[{where} SEC. {meta['section']}, p. {meta['page_start']}]"
        return f"[{meta['doc_id']}, p. {meta['page_start']}]"

    lines = [CITATION.sub(expand, answer.text), ""]

    if answer.unverified:
        lines.append(f"WARNING  unverifiable citations: {', '.join(answer.unverified)}")
    if answer.abstained and not answer.refused:
        lines.append("(no sources cited - treated as an abstention)")

    sources = [(c, by_id[c]) for c in answer.cited_ids if c in by_id]
    if sources:
        lines.append("Sources:")
        for _, meta in sources:
            if meta.get("section"):
                where = meta["doc_id"]
                if meta.get("title"):
                    where += f" Title {meta['title']}"
                where += f" SEC. {meta['section']} (p. {meta['page_start']})"
            else:
                where = f"{meta['doc_id']} p. {meta['page_start']}"
            lines.append(f"  - [{meta['authority']}] {where}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:])
    if not question:
        print("usage: python answer.py <question>")
        raise SystemExit(1)

    try:
        pipeline = Pipeline()
    except MissingCredentials as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from None

    print(render(pipeline.ask(question)))
