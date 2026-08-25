# Legislation RAG

Question answering over H.R. 1 (the "One Big Beautiful Bill Act"), across three
legislative versions of the bill plus a Council of Economic Advisers report
about it. Answers are cited to a specific document, section and page, and
labelled by whether the source is enacted law, a draft proposal, or advocacy.

## Install

```bash
./setup.sh
```

Creates a virtualenv, installs dependencies, installs Tesseract if missing, and
builds the index from the PDFs in `data/raw/`. Takes about five minutes, most of
it embedding 2,365 chunks.

Then add an API key for the generation step:

```bash
cp .env.example .env    # then edit .env and paste your key
```

Get one at <https://console.anthropic.com/settings/keys>. Retrieval works
without a key; only answer generation needs it.

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
.venv/bin/python src/evaluate.py          # all 11 questions
.venv/bin/python src/evaluate.py --only tips-cap
```

Questions and hand-verified expected citations are in
[`eval/eval_set.yaml`](eval/eval_set.yaml); results with full answers are in
[`eval/RESULTS.md`](eval/RESULTS.md).

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

70 tests. No API key needed — the LLM call is not tested, the logic around it
is.

## Layout

```
config/manifest.yaml   Document provenance. Hand-written; `authority` drives everything.
src/ingest.py          Per-page extraction, OCR fallback, margin-number removal
src/chunk.py           Section-boundary chunking
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

Four PDFs, 2,413 pages, in `data/raw/`:

| Document | Pages | What it is |
|---|---|---|
| `BILLS-119hr1enr.pdf` | 330 | H.R. 1 **enrolled** — the enacted law |
| `Xthe_one_big_beautiful_bill_act.pdf` | 940 | Senate substitute amendment (draft) |
| `Xone_big_beautiful_bill_act_-_full_bill_text.pdf` | 1,116 | House-passed text (draft) |
| `XThe-One-Big-Beautiful-Bill-...-1.pdf` | 27 | CEA report — advocacy, image-only, OCR'd |

Three of the four are the same bill at different stages. That is the central
problem this pipeline is built around; see [WRITEUP.md](WRITEUP.md).
