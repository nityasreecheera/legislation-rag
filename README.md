# Legislation RAG

Question answering over seven legislative documents in two jurisdictions: H.R. 1
(the federal "One Big Beautiful Bill Act") in three versions, a Council of
Economic Advisers report about it, and three Arizona state bills. Answers are
cited to a specific document, section and page, and labelled by whether the
source is enacted law, a draft proposal, or advocacy - and by which jurisdiction
it belongs to.

## Quickstart

```bash
unzip legislation-rag.zip && cd legislation-rag
./setup.sh                                    # ~5 min, builds the index
cp .env.example .env                          # paste an Anthropic API key into it
.venv/bin/python src/chat.py                  # ask questions
```

Needs **Python 3.10+** and macOS or Linux. `setup.sh` installs Tesseract via
Homebrew if it is missing; on Linux use `apt install tesseract-ocr` first. The
source documents are in the repo, so nothing else has to be downloaded.

## Install

```bash
./setup.sh
```

Creates a virtualenv, installs dependencies, installs Tesseract if missing, and
builds the index from the documents in `data/raw/`. Takes about five minutes,
most of it embedding 2,383 chunks. Run it again any time to rebuild from
scratch.

Then add an API key for the generation step:

```bash
cp .env.example .env    # then edit .env and paste your key
```

Get one at <https://console.anthropic.com/settings/keys>. Without a key the chat
exits with instructions rather than a stack trace.

**Retrieval works without a key** — only answer generation needs one:

```bash
.venv/bin/python src/retrieve.py "tips deduction cap"   # ranked chunks + scores
.venv/bin/python src/diff.py --from house               # version comparison
```

## Run

```bash
.venv/bin/python src/chat.py
```

An interactive shell:

```
> What is the cap on the tips deduction?

$25,000 per taxable year, under SEC. 70201 of the enrolled bill
[hr1-enrolled Title VII SEC. 70201, p. 99]. That cap is reduced by $100 for
each $1,000 by which modified AGI exceeds $150,000 ($300,000 joint)...

Sources:
  - [law] hr1-enrolled Title VII SEC. 70201 (p. 99)

> :sources
```

### Shell commands

| Command | Effect |
|---|---|
| `:sources` | Chunks retrieved for the last answer, with scores; `*` marks the cited ones |
| `:authority law\|proposal\|advocacy\|all` | Restrict retrieval by source type |
| `:jurisdiction federal\|arizona\|all` | Restrict retrieval by jurisdiction |
| `:k <n>` | Chunks retrieved per question (default 8) |
| `:history` | Questions asked so far |
| `:clear` | Forget the conversation |
| `:quit` | Exit |

### One-shot

```bash
.venv/bin/python src/answer.py "Does H.R. 1 eliminate tax on tips?"
```

## Comparing bill versions

Retrieval can tell you what a document says. It cannot tell you what is
*missing* from one — eight retrieved chunks say nothing about the other 2,357.
`diff.py` works over the whole corpus instead:

```bash
.venv/bin/python src/diff.py --from house
.venv/bin/python src/diff.py --from house --status no_counterpart
.venv/bin/python src/diff.py --from senate --json
```

It matches every provision in a draft against the enacted bill on three signals
— heading, wording, and which statute it amends — and sorts them:

| Bucket | Meaning |
|---|---|
| `enacted` | Heading matches an enrolled section |
| `likely_renamed` | Different title, strong text or statute match; counterpart named |
| `needs_review` | Ambiguous — best candidate shown, human decides |
| `no_counterpart` | Nothing close on either signal — evidence of a drop |

It will not assert that a provision was dropped. No signal tested separates
"renamed" from "dropped" reliably, so ambiguous cases go to `needs_review`
rather than getting a confident label. See [WRITEUP.md](WRITEUP.md).

## Evaluation

```bash
.venv/bin/python src/evaluate.py          # all 15 questions
.venv/bin/python src/evaluate.py --only tips-cap
```

Questions and hand-verified expected citations are in
[`eval/eval_set.yaml`](eval/eval_set.yaml); results with full answers are in
[`eval/RESULTS.md`](eval/RESULTS.md).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

80 tests. No API key needed — the LLM call is not tested, the logic around it
is.

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

Reasoning behind each choice is in [WRITEUP.md](WRITEUP.md).

## Layout

```
config/manifest.yaml   Document provenance. Hand-written; `authority` drives everything.
src/ingest.py          Per-page extraction, OCR fallback, HTML/MHTML, margin-number removal
src/chunk.py           Section-boundary chunking (federal and state numbering)
src/index.py           Chroma (dense) + BM25 (lexical)
src/retrieve.py        RRF fusion, version grouping, section reassembly
src/answer.py          Grounded generation + citation verification
src/chat.py            Interactive shell
src/diff.py            Provision-level version comparison
src/evaluate.py        Eval harness
eval/                  Question set and recorded results
```

Design decisions and their reasoning are in [WRITEUP.md](WRITEUP.md).

## Rebuilding

`setup.sh` runs these in order; they can be run individually after changing a
stage:

```bash
.venv/bin/python src/ingest.py    # PDFs      -> data/extracted/*.jsonl   (~2 min)
.venv/bin/python src/chunk.py     # pages     -> data/chunks.jsonl
.venv/bin/python src/index.py     # chunks    -> Chroma + BM25            (~2 min)
```

## Corpus

Seven documents, three formats, two jurisdictions, ~2,425 pages, in `data/raw/`:

| Document | Size | Format | What it is |
|---|---|---|---|
| `BILLS-119hr1enr.pdf` | 330 pp | PDF | H.R. 1 **enrolled** — the enacted law |
| `Xthe_one_big_beautiful_bill_act.pdf` | 940 pp | PDF | Senate substitute amendment (draft) |
| `Xone_big_beautiful_bill_act_-_full_bill_text.pdf` | 1,116 pp | PDF | House-passed text (draft) |
| `XThe-One-Big-Beautiful-Bill-...-1.pdf` | 27 pp | PDF (image-only) | CEA report — advocacy, OCR'd |
| `SB1229S– "Arizona Starter Homes Act".pdf` | 4 pp | PDF | AZ SB 1229, engrossed |
| `HB2681 - 571R - H Ver ....mhtml` | ~5 pp | **MHTML** | AZ HB 2681, engrossed |
| `Arizona-2025-SB1111-Engrossed-....html` | ~3 pp | **HTML** | AZ SB 1111, engrossed |

Three of the seven are the same bill at different stages — the central problem
this pipeline is built around. The Arizona bills add a second jurisdiction and
the only non-PDF inputs. See [WRITEUP.md](WRITEUP.md).

Note on the last one: it is a strike-everything amendment, so its own caption
("nonhealth regulatory boards") no longer matches its enacting text (a fee on
foreign wire transfers). Only the operative text is reliable.
