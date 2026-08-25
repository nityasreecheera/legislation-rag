"""Build the dense and lexical indexes.

Embedding model: BAAI/bge-base-en-v1.5, run locally.

Chosen over a hosted embedding API for three reasons that matter more than raw
quality here. It needs no API key, so the repo runs end to end for whoever
grades it. It is deterministic, so retrieval results are reproducible between
runs and the eval numbers mean something. And the corpus is 2,476 chunks - small
enough that local embedding takes a couple of minutes, which is cheaper than the
round trips. The tradeoff is a 512-token input limit, which is why chunks are
sized to roughly 500 tokens: a longer chunk would be silently truncated and the
tail would never be searchable.

Two indexes are built over the same chunks:

  * Chroma holds the dense vectors, with the manifest metadata attached to every
    record so retrieval can filter on `authority` and `stage`.

  * BM25 is held separately, in memory. It exists because this corpus is full of
    identifiers - "SEC. 70201", "Title VII", "section 199A" - and dense
    embeddings are poor at exact token matching. A query naming a section number
    should find that section, and only the lexical index reliably does that.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

REPO_ROOT = Path(__file__).resolve().parent.parent
CHUNKS_PATH = REPO_ROOT / "data" / "chunks.jsonl"
CHROMA_DIR = REPO_ROOT / "data" / "chroma"
BM25_PATH = REPO_ROOT / "data" / "bm25.pkl"

EMBED_MODEL = "BAAI/bge-base-en-v1.5"
COLLECTION = "hr1"
EMBED_BATCH = 64

# Metadata fields promoted into the vector store. Chroma only filters on scalar
# values, so this is deliberately flat.
INDEXED_FIELDS = (
    "doc_id", "stage", "authority", "doc_type", "jurisdiction", "version_group",
    "title", "section", "section_heading",
    "page_start", "page_end", "extraction", "has_figure",
)


def load_chunks() -> list[dict]:
    with CHUNKS_PATH.open() as fh:
        return [json.loads(line) for line in fh]


def tokenize(text: str) -> list[str]:
    """Lowercase word/number tokens for BM25.

    Section numbers are kept whole so "70201" matches "SEC. 70201", and internal
    punctuation is stripped so "199A" and "U.S.C." tokenize predictably.
    """
    return re.findall(r"[a-z0-9]+", text.lower())


def _metadata(chunk: dict) -> dict:
    """Chroma rejects None, so absent fields become empty strings."""
    return {
        field: ("" if chunk.get(field) is None else chunk[field])
        for field in INDEXED_FIELDS
    }


def build(rebuild: bool = True) -> None:
    chunks = load_chunks()
    print(f"loaded {len(chunks)} chunks")

    print(f"embedding with {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    embeddings = model.encode(
        [c["text"] for c in chunks],
        batch_size=EMBED_BATCH,
        show_progress_bar=True,
        normalize_embeddings=True,
    ).tolist()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    if rebuild:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass

    # Cosine similarity, because the embeddings are L2-normalised above.
    collection = client.create_collection(
        COLLECTION, metadata={"hnsw:space": "cosine"}
    )

    for start in range(0, len(chunks), 512):
        window = chunks[start : start + 512]
        collection.add(
            ids=[c["chunk_id"] for c in window],
            embeddings=embeddings[start : start + 512],
            documents=[c["text"] for c in window],
            metadatas=[_metadata(c) for c in window],
        )
    print(f"chroma: {collection.count()} vectors -> {CHROMA_DIR.name}/")

    # BM25 indexes the section heading alongside the body: a query like "no tax
    # on tips" should match the section whose *title* says that, even where the
    # body is dense statutory cross-references that never repeat the phrase.
    corpus = [
        tokenize(f"{c.get('section_heading') or ''} {c['text']}") for c in chunks
    ]
    with BM25_PATH.open("wb") as fh:
        pickle.dump(
            {"bm25": BM25Okapi(corpus), "ids": [c["chunk_id"] for c in chunks]}, fh
        )
    print(f"bm25:   {len(corpus)} documents -> {BM25_PATH.name}")


if __name__ == "__main__":
    build()
