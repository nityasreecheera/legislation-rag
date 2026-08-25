"""Run a list of questions and save full transcripts.

Answers are expensive to regenerate, so every run is written to disk with its
citations and verification status. The saved transcripts are what the write-up
quotes from.
"""
import json, sys, datetime
from pathlib import Path
from answer import Pipeline, render

OUT = Path(__file__).resolve().parent.parent / "data" / "eval_runs"

def main(questions: list[str]) -> None:
    pipeline = Pipeline()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    records = []
    for i, question in enumerate(questions, 1):
        print(f"[{i}/{len(questions)}] {question}", flush=True)
        answer = pipeline.ask(question)
        records.append({
            "question": question,
            "answer": answer.text,
            "rendered": render(answer),
            "cited_ids": answer.cited_ids,
            "unverified": answer.unverified,
            "grounded": answer.grounded,
            "abstained": answer.abstained,
            "retrieved": [
                {"chunk_id": r.chunk_id, "authority": r.metadata["authority"],
                 "citation": r.citation, "score": round(r.score, 5)}
                for r in answer.results
            ],
        })
    path = OUT / f"run-{stamp}.json"
    path.write_text(json.dumps(records, indent=2))
    print(f"\nsaved -> {path.relative_to(path.parent.parent.parent)}")

if __name__ == "__main__":
    main([l.strip() for l in sys.stdin if l.strip()])
