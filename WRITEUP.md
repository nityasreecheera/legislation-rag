# Write-up

**Time spent: roughly 14 hours.** The first of those went on reading the corpus
before writing any code, and it was the most useful hour of the fourteen — the
version-collision problem that shaped every later decision was visible in the
documents long before it showed up in a retrieval result.

---

## The problem this corpus actually poses

The assignment reads like a document-QA problem. This corpus isn't one.

Three of the seven documents are **the same bill** — H.R. 1 — captured at
different legislative stages:

| Document | Pages | Format | Status |
|---|---|---|---|
| House-passed text | 1,116 | PDF | draft; 43% of it never became law |
| Senate substitute | 940 | PDF | draft; replaced the House text wholesale |
| Enrolled | 330 | PDF | **the enacted law** |
| CEA report | 27 | PDF (image-only) | advocacy *about* the bill |
| AZ SB 1229 | 4 | PDF | state bill, engrossed |
| AZ HB 2681 | ~5 | **MHTML** | state bill, engrossed |
| AZ SB 1111 | ~3 | **HTML** | state bill, engrossed |

The first three have near-identical text. That breaks retrieval in a way that isn't obvious
until you watch it happen: a query for "no tax on tips" returns the same
provision three times, at nearly indistinguishable similarity scores, from three
documents. The top-5 becomes one provision repeated, and four relevant
provisions never surface.

Worse, the numbering collides. **`SEC. 70201` is "No Tax on Tips" in the enrolled
bill and "Congressional Review Act Compliance" in the House draft** — entirely
different provisions under one number. Each chamber organises the bill by *its
own* committees, so Title IV means Energy & Commerce in one document and
Commerce/Science/Transportation in another. A citation reading "H.R. 1, Title
IV, SEC. 70201" is meaningless without naming the version.

Measured across the corpus: 106 provisions appear in all three versions, 198 in
exactly two, and **263 in only one**. So for a randomly chosen provision, the
odds are good that it exists in some versions and not others.

**The central design consequence:** embeddings capture *what a passage says*.
They cannot capture *which version said it*, which is the only thing that
matters here. No embedding model fixes this. Metadata does.

The Arizona bills sharpen the same point from a different angle. They are
`proposal` — engrossed, passed one chamber, not law — exactly the label the
federal drafts carry. Without a second axis they collapse into one category, and
"an earlier House draft would have..." becomes indistinguishable from "an
Arizona bill would have...". Hence `jurisdiction`. The eval question that proves
it: asked whether *federal* law restricts municipal home design, the pipeline
declines, then volunteers that Arizona SB 1229 does — flagged as state, and as
not enacted.

---

## Architecture

```
  7 documents · PDF, HTML, MHTML · 2 jurisdictions
                       │
      ┌────────────────▼────────────────┐
      │ 1. INGEST                       │   per page: text, or OCR if < 100 chars
      │    ingest.py                    │   strip margin line numbers (by x-position)
      └────────────────┬────────────────┘   MIME-decode MHTML
                       │                     → one record per page
      ┌────────────────▼────────────────┐
      │ 2. CHUNK                        │   split on SEC. boundaries, never across
      │    chunk.py                     │   window long sections (2000c / 300 overlap)
      └────────────────┬────────────────┘   stamp authority · jurisdiction · section · page
                       │                     → 2,383 chunks
      ┌────────────────▼────────────────┐
      │ 3. INDEX                        │   Chroma   768-d vectors   (meaning)
      │    index.py                     │   BM25     term counts     (exact strings)
      └────────────────┬────────────────┘
                       │
      ┌────────────────▼────────────────┐
      │ 4. RETRIEVE                     │   a. query both indexes
      │    retrieve.py                  │   b. fuse by rank (RRF)
      │                                 │   c. group versions of one provision
      │                                 │   d. cap advocacy at 25% of slots
      └────────────────┬────────────────┘   e. reassemble each section from its chunks
                       │                     → 8 provisions
      ┌────────────────▼────────────────┐
      │ 5. ANSWER                       │   Claude Opus 5
      │    answer.py                    │   prompt enforces law / proposal / advocacy
      └────────────────┬────────────────┘
                       │
      ┌────────────────▼────────────────┐
      │ 6. VERIFY                       │   every cited ID must be one that was retrieved
      │    answer.py                    │   unresolvable ones flagged, not rendered
      └────────────────┬────────────────┘
                       ▼
         cited answer, labelled by authority

  Steps c, d and e exist only because this corpus holds the same bill
  three times. Steps 1-2 and 3 are ordinary RAG.
```

Provenance is attached at ingest from a hand-written manifest
(`config/manifest.yaml`) and carried through every stage to the citation. The
field that does the work is `authority`:

| Value | Meaning | Rule at answer time |
|---|---|---|
| `law` | Enrolled text | Only these may be described as what the law does |
| `proposal` | House / Senate draft | Must be framed as "the House version proposed…" |
| `advocacy` | CEA report | Must be attributed as a projection, never as law |

A second axis, `jurisdiction` (`federal` / `arizona`), keeps a state bill from
answering a federal question. Two further manifest fields keep document
conventions out of the code: `section_style` selects the numbering pattern
(federal `SEC. 70201.` vs state `Section 1.`), and `version_group` marks which
documents are versions of the *same* bill — only those may be collapsed
together during retrieval.

The manifest is written by hand, not inferred. There are seven documents;
a classifier would add a failure mode to save no work. At 10,000 documents this
inverts — see the scale section.

---

## Chunking

**Section boundaries, with windowing inside long sections.** Not fixed-size, not
recursive-character.

Every substantive provision lives under a numbered section (`SEC. 70201.`), and
that number is what a reader would actually cite. So a chunk never spans two
sections, even where a short section could be merged with its neighbour to pack
context more efficiently. A chunk straddling a boundary produces a citation
pointing at two provisions at once, which is worse than a slightly wasteful
chunk.

Sections longer than 2,000 characters split into overlapping windows, preferring
paragraph breaks so a window rarely starts mid-sentence.

**Why 2,000 chars / 300 overlap (~500 / 75 tokens):** derived from the embedding
model's 512-token input limit. Anything longer is silently truncated and its
tail becomes permanently unsearchable. The size is a consequence of that
constraint, not a preference.

- **Too small breaks this:** SEC. 70201 is already 7 chunks, with the $25,000
  cap and the income phase-out in *different* chunks. Smaller and you retrieve
  "the deduction is capped" without the number.
- **Too large breaks this:** a 4,000-char chunk spanning three subsections
  produces a vector that is the average of three topics — weakly similar to
  everything, strongly similar to nothing. Citations also get coarser.

The CEA report has no sections, so it chunks per page. Its page number is the
only citation anchor available.

Arizona bills number sections plainly — `Section 1.` then `Sec. 2.` — which the
federal pattern cannot match, since its 5-6 digit constraint exists precisely to
exclude short numbers like cross-references. Rather than run both patterns and
hope, `section_style` in the manifest says which applies. The web documents have
no pages at all, so the whole document is one record and the section becomes the
citation anchor — which is the better anchor anyway.

### Two extraction bugs worth naming

Both were silent — they produced a quietly smaller corpus rather than an error.

**Justified headers.** Four section headings are stretched to fill the page
width, which the extractor renders as a newline between every word:
`SEC. \n70102. \nEXTENSION \nAND \n...`. The header pattern required a space, so
those four sections were never chunked at all. Nothing failed; the corpus was
just missing them.

**Line numbers in the margin.** The two draft bills are typeset with line
numbers down the left edge, which extraction interleaves into the prose —
`COMMUNITY-BASED 13 SERVICES`. This corrupted headings, and headings are the
cross-version join key, so polluted ones failed to match their counterparts.

The fix was positional rather than a regex guess: measured geometry shows line
numbers are numeric tokens at x0 = 126/133 while body text starts at x0 ≥ 196.
Margin numerics are dropped, and only for documents where line numbers are
actually detected — a no-op on the enrolled bill.

---

## Embedding

**`BAAI/bge-base-en-v1.5`, run locally.** 768 dimensions, cosine similarity.

The driver was **reproducibility, not quality.** It needs no API key, so the
repo runs end to end for whoever grades it, and it produces identical vectors
every run, which is what makes the eval numbers comparable between runs. Cost
(free) and latency (96 seconds for 2,365 chunks, one-time) were secondary.

Choosing on something other than quality is defensible here because **the
embedding model is not the bottleneck on this corpus.** Queries name section
numbers and exact legal terms, where BM25 beats dense retrieval outright. And no
embedding, however good, distinguishes three near-identical copies of the same
provision.

A hosted model (Voyage, or a larger BGE) would retrieve better on dense
legalese. It would not fix version disambiguation.

---

## Retrieval

**Hybrid: BM25 + dense, fused with Reciprocal Rank Fusion.** RRF rather than a
weighted score blend because cosine similarities and BM25 scores are on
incompatible scales, and normalising them introduces a tuning parameter that
would need a labelled set to fit. RRF only needs the rankings.

BM25 earns its place on this corpus specifically: a query naming `SEC. 70201`
should find that section, and dense embeddings are unreliable at exact token
matching.

Three corpus-specific steps run after fusion.

### Version grouping

Chunks describing the same provision are collapsed into one result carrying its
variants, so top-k counts *distinct provisions* rather than distinct documents.
Enacted text leads each group; drafts follow in legislative order, still
attached so a "what changed" question remains answerable.

The join key is the **section heading**, not the section number — the same
provision is `SEC. 70201` in the enrolled bill and `SEC. 110101` in the House
draft, but both are titled `NO TAX ON TIPS.`

### Advocacy cap

The CEA report is 59 chunks against 2,306 of statute, but it won **four of the
top five slots** on the first real query, pushing the enacted law to second.

The cause is visible in the text. CEA writes in the language people ask
questions in ("tax on tips", "take-home pay"); the provision that actually does
it reads *"Part VII of subchapter B of chapter 1 is amended by redesignating
section 224 as section 225."* Relevant, and lexically nothing like the query.

Advocacy is capped at 25% of top-k — reachable for questions it genuinely
answers, unable to crowd out statute on questions about what the law says.

### Section reassembly

Once any chunk of a section is retrieved, its remaining chunks are pulled in and
the provision is reassembled in document order. Retrieval still ranks by chunk;
the unit handed to the model is the provision.

This was added late, after the interactive shell exposed the failure: asking
"what is the cap on the tips deduction?" retrieved the definitional chunks of
SEC. 70201 and missed the one containing `$25,000`. The answer reported —
accurately, and uselessly — that the cap "isn't in the excerpts I have". The
same question in different words had worked, which meant the eval had been
passing it by luck of phrasing.

---

## Version diffing — and why it is triage, not a classifier

Retrieval cannot answer the most interesting question about this corpus: *what
was in the House bill that didn't become law?* Proving absence requires
exhaustive access, and top-k retrieval is definitionally non-exhaustive — eight
chunks say nothing about the other 2,357. Asked directly, the pipeline declines,
correctly, on exactly those grounds.

`src/diff.py` works over the whole corpus instead. It was meant to be a
classifier. It is not, and the reason is the most useful thing I learned.

Three signals, each failing where the others work:

| Signal | Failure |
|---|---|
| Heading match | Reports 246 of 351 House provisions missing. "MAGA ACCOUNTS" was not dropped — it became "Trump accounts" |
| Text similarity | Scores MAGA at 0.788 → "dropped". The rename runs through the whole provision, dragging the embedding off its own counterpart |
| Statutory fingerprint | Both create IRC §530A, but at any threshold low enough to catch that (0.54), it also matches §899 "unfair foreign taxes" (0.62) — which really was dropped — to an unrelated provision sharing references incidentally |

A fourth attempt — scoring by the single rarest shared reference — was worse:
nearly every provision shares some code with some enrolled section, so scores
saturated and matches became arbitrary.

**The blocking fact: a provision that survived scores lower than one that
died.** No threshold separates them. Continuing to tune would have meant fitting
to the four cases I had already hand-verified — accurate-looking, and
generalising to nothing.

So the confident classes stay confident (`enacted`, `likely_renamed`,
`no_counterpart`) and everything ambiguous goes to `needs_review` with its best
candidate attached. The tested property is not label accuracy but that **no
hand-verified survivor is ever labelled `no_counterpart`** — telling a reader a
policy is dead when it is law is the damaging error.

One real bug the tests caught: cosine similarity saturates at 1.0 when two
provisions share exactly one reference, because normalisation cancels the IDF
weight meant to suppress a worthless match on "section 1". Fixed by scaling with
the shared IDF mass.

## Grounding

Two mechanisms, neither of them the prompt alone.

**Citation verification.** Every cited chunk id must resolve to a chunk that was
actually in the context window. Ids that don't are surfaced as `UNVERIFIED`
rather than rendered. Cheap, and it catches the specific failure the rubric
names — a fluent answer carrying a citation that doesn't support it.

**Authority-aware prompting.** The prompt's main job is not accuracy in the
usual sense; it is refusing to describe a dropped draft provision, or a CEA
projection, as what the law says.

### The citation bug this caught

An early answer said *"the same provision appears as SEC. 70201 in the Senate
substitute"* — while citing the **enrolled** chunk. Right fact, wrong document
pointed at. The verifier passed it, because the cited id genuinely was in
context.

The cause: version variants were shown in the prompt as prose with no citable
id, so the model attached the claim to the nearest one. Fixed by giving variants
their own ids. The answer now cites the Senate document and volunteers the
limit: *"their texts were not retrieved, so I can't say how they differed."*

---

## Edge cases

| Case | Handling |
|---|---|
| Empty query | Short-circuits before retrieval and before any API call (tested) |
| Question spanning documents | Version grouping surfaces all versions of a provision together |
| Conflicting information | Three bill versions with genuinely different content; answers separate them by stage |
| Answer not in documents | Explicit abstention with what would be needed |
| Ambiguous section number | `SEC. 70201` resolves to two different provisions; both returned, labelled |
| Image-only document | Per-page OCR fallback, 94.3% mean confidence |

---

## Interface

An interactive shell (`src/chat.py`) rather than a web UI. The terminal shows
everything a page would, and `:sources` — which dumps the retrieved chunks with
their scores and marks the cited ones — is the only way to tell a good answer
from a lucky one. That mattered more than polish.

Conversation memory is deliberately narrow. A follow-up like "what about
overtime?" has no content words for a retriever to match, so it is rewritten
into a standalone query against the conversation *before* retrieval — "what is
the cap on the overtime deduction in the enrolled bill?" Prior turns replay as
context, but **prior excerpts do not**: carrying them forward would grow context
without bound and let a chunk retrieved for a different question be cited as
evidence for this one.

---

## Evaluation

15 questions, hand-verified ground truth, in `eval/eval_set.yaml`. Weighted
toward this corpus's failure modes: four turn on distinguishing law from draft,
three require declining (two out-of-corpus, one cross-jurisdiction), two require
attributing advocacy, one checks the non-PDF ingestion path end to end, one
checks that a strike-everything amendment is read from its enacting text rather
than its stale caption, and only four are plain lookups.

**Result: accuracy 14/15 (93%), grounded 15/15 (100%), citation recall 96%.**

| Metric | Value | Definition |
|---|---|---|
| Accuracy | 14/15 (93%) | Every check passed for the question |
| Grounded | 15/15 (100%) | No citation points at an unretrieved chunk |
| Citation recall | 96% | Expected sources cited, over the 12 questions that have them |

None of these measures whether a claim is *true* — only whether its citation
resolves, whether the answer declined when it should have, and whether the
required framing appeared. That gap is precisely what let question 6 pass while
being useless.

**The one failure is the most useful result in the set.**
`anniversary-version-diff` asks whether the House and enacted versions funded the
250th anniversary the same way. The answer was *"I can't compare them - I only
have the enacted text ... only their location was retrieved, not their text."*
Honest, and a failure.

It scored as a **pass** until I looked at the text. Version grouping hands the
model a citable id for each variant but not its content, and the scorer treated
citing that id as evidence the section had been retrieved. So a capability that
does not work reported 100% recall.

The consequence is larger than one question: **the entire `version_comparison`
category is currently unanswerable.** Comparing two versions requires both texts
in context, and grouping deliberately supplies only one. The fix is to fetch
variant text for the top few grouped results, at the cost of tripling their
tokens. Not built - flagged rather than papered over.

Two further questions initially failed for reasons that were bugs in my
*evaluation* rather than the pipeline:

1. I wrote an abstention question about climate change, reasoning that the
   phrase "climate change" has zero matches in the corpus. The pipeline
   "failed" it by answering — correctly. The bill rescinds Inflation Reduction
   Act climate funding (SEC. 60018) and amends the §45Z clean fuel credit.
   **Absence of a phrase is not absence of a topic.** Refusing would have been
   the worse answer. The question was reframed to test scope-limited answering
   instead.

2. I scored abstention as "cited nothing". The best abstention the pipeline
   produced cited **six** chunks — to show what it had searched, and to rule out
   §280C, one character from the §280E the question asked about. That is more
   useful than a bare refusal, and my metric was calling it a failure.
   Abstention is now judged on whether the answer declines in words.

So the measurement was adjusted three times after seeing behaviour - twice
because it was too strict, once because it was too lenient and hid a real
failure. That is a mild form of overfitting, and the score partly reflects a set
that learned what the system does. It is a floor on obvious failure, not a quality score.

Other limits: 15 questions is small; phrase matching is crude and catches
blatant framing errors, not subtle ones; and the person who wrote the questions
also built the system.

---

## Known limitations

**Charts are not extracted.** OCR reads glyphs, so a figure yields axis labels
and a title with every relationship stripped out — `11 9 7 5 3 2010:Q1`. Pages
containing figures are flagged, but the orphaned numbers remain in their chunks
and could in principle be cited as though meaningful.

**OCR quality is capped by the source.** The CEA report is 144 DPI. Rendering at
300 improves segmentation but recovers no detail that isn't there. Body text is
essentially character-perfect; footnotes and small chart labels are weaker.

**A document can disagree with itself.** Arizona SB 1111 is a strike-everything
amendment: its caption still reads "nonhealth regulatory boards; challenges;
prohibition (now: ______)" and its purpose clause reads "relating to
_______________", both left blank when the original text was struck. Its
operative text adds ARTICLE 3, "ILLEGAL ALIEN REMITTANCE FEE", to Title 6
Chapter 12 A.R.S.

I initially recorded this backwards in the manifest — assuming, reasonably, that
a document's own caption outranks a filename someone typed. It does not here:
the filename described the current content and the caption was the stale half.
The pipeline got it right anyway, because it reads enacting text rather than
labels. The general lesson is narrower than "trust the document over the
filename": under a striker, only the operative text is reliable, and any
metadata field can be a fossil.

**The advocacy cap is a blunt instrument.** 25% is a judgement, not a fitted
parameter. A question genuinely about CEA's modelling gets fewer of its sources
than it should unless `:authority advocacy` is set explicitly.

**Cross-version grouping relies on heading text**, scoped by `version_group` so
only versions of the same bill can collapse together. Adding the Arizona bills
turned that from a hypothetical into a necessary fix: "Short title" appears in
several of them, and without scoping, one bill's short-title section would have
been presented as a variant of another's. Within a version group the heading is
still the join key, so a provision renamed *and* renumbered between versions
would still be missed.

**Scope is still narrowed.** The assignment also supplied two California bills
(182 pages). I left them out: they are more PDF, demonstrating nothing the
pipeline cannot already do, and California's absence is what makes one of the
abstention tests real. Arizona was worth adding because 12 pages bought two new
input formats and a second jurisdiction.

**Conversation memory is narrow.** Prior turns replay for context, but prior
excerpts do not, so a follow-up cannot cite something retrieved two turns ago.
Deliberate — carrying excerpts forward would let a chunk retrieved for a
different question be cited as evidence here — but it does mean some natural
follow-ups re-retrieve unnecessarily.

**No reranker.** A cross-encoder over the fused candidates would likely improve
ordering. It was not the bottleneck; metadata was.

**Section reassembly has no budget.** Pulling every sibling chunk of a retrieved
section is fine when the longest section is 7 chunks. A statute with a
hundred-page section would blow the context window; the cap is a character limit
rather than a relevance-ordered fallback.

**The diff tool leaves most provisions unclassified.** 185 of 351 land in
`needs_review`. That is honest rather than useless — a ranked shortlist with
suggested counterparts beats reading 1,116 pages — but it is triage, not an
answer.

---

## What I'd change with another week

1. **Sharpen the version diff.** `src/diff.py` now exists but leaves 185 of 351
   provisions in `needs_review`. The signal most likely to close that gap is
   structural: parse the amendatory language itself ("Section X is amended by
   striking Y") rather than inferring intent from prose similarity. That is a
   parser, not a model, and it would be exact where the current approach is
   probabilistic.
2. **Ground figures with a vision model.** One pass over the 4 figure pages,
   reading each chart into a structured description, closes the only gap where
   the pipeline silently holds meaningless data.
3. **Write the eval before looking at any output.** Both eval bugs came from
   calibrating after the fact.
4. **A retrieval-only eval.** Current metrics measure the whole pipeline, so a
   retrieval regression can hide behind a model that compensates. Recall@k
   against known-relevant sections would separate the two.
5. **Adversarial grounding tests.** Deliberately feed the model an authority
   label that contradicts the text and confirm it follows the label. Right now
   authority handling is verified only by observation.

## What breaks first at 10,000 documents

In the order it would actually hurt:

1. **The manifest.** Hand-written provenance is right for four documents and
   impossible for 10,000. The `authority` field — which the entire design rests
   on — would have to come from document metadata or a classifier, and that
   classifier's accuracy becomes the pipeline's accuracy ceiling. This is the
   real scaling problem, and it is not an infrastructure one.
2. **BM25.** Currently an in-memory `rank_bm25` object pickled to disk and
   rebuilt wholesale. It would need a real inverted index — OpenSearch, or
   Postgres full-text — with incremental updates.
3. **The heading join key.** "SHORT TITLE" appears in every bill ever written.
   Cross-version grouping would need scoping by bill identity, not just heading.
4. **Re-embedding.** 96 seconds now, hours then. Any chunker change currently
   rebuilds everything; it would need incremental indexing keyed on content
   hash.
5. **Section reassembly.** Pulling every sibling chunk is fine when sections are
   7 chunks. Some statutes have sections running hundreds of pages, so it would
   need a budget and a relevance-ordered fallback.

**What does not break: the vector store.** Chroma at 2,365 vectors is trivial,
and HNSW handles millions. It is the component people expect to name first, and
it is the last one I would worry about here.
