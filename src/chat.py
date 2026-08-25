"""Interactive shell for querying the corpus.

Loads the embedding model and indexes once, then stays open. Beyond
convenience, this exists so the retrieval layer can be inspected while asking
questions - `:sources` shows what was actually retrieved and how it scored,
which is the only way to tell a good answer from a lucky one.

Conversation memory is deliberately narrow. Prior turns are replayed so
follow-ups resolve ("what about overtime?"), and the follow-up is rewritten
into a standalone query before retrieval, because a retriever cannot match on a
question with no content words. But excerpts from earlier turns are NOT
replayed: only the current turn's retrieved chunks are citable. Carrying old
excerpts forward would grow context without bound and, worse, let the model
cite a chunk that was retrieved for a different question.
"""

from __future__ import annotations

import sys

from answer import HISTORY_TURNS, MissingCredentials, Pipeline, Turn, render

BANNER = """\
Legislation RAG - H.R. 1 corpus
Type a question, or :help for commands. Ctrl-D to exit.
"""

HELP = """\
Commands
  :sources            what was retrieved for the last answer, with scores
  :authority <level>  restrict retrieval - law | proposal | advocacy | all
  :jurisdiction <j>   restrict retrieval - federal | arizona | all
  :k <n>              chunks retrieved per question (default 8)
  :history            questions asked so far
  :clear              forget the conversation
  :help               this
  :quit               exit

Authority levels
  law        the enrolled bill - what the statute actually says
  proposal   House / Senate drafts and Arizona bills - not enacted
  advocacy   the CEA report - projections, not law

Jurisdictions
  federal    H.R. 1 and the CEA report
  arizona    three state bills, all engrossed
"""


class Shell:
    def __init__(self) -> None:
        self.pipeline = Pipeline()
        self.history: list[Turn] = []
        self.last = None
        self.authority: str | None = None
        self.jurisdiction: str | None = None
        self.k = 8

    # -- commands --------------------------------------------------------------

    def show_sources(self) -> None:
        if not self.last or not self.last.results:
            print("No results yet.")
            return

        if self.last.retrieval_query != self.last.question:
            print(f"retrieval query: {self.last.retrieval_query!r}\n")

        cited = set(self.last.cited_ids)
        for i, result in enumerate(self.last.results, 1):
            meta = result.metadata
            mark = "*" if result.chunk_id in cited else " "
            print(f"{mark}{i}. [{meta['authority']:8s}] {result.citation}  {result.score:.4f}")
            if meta.get("section_heading"):
                print(f"     {meta['section_heading']}")
            for variant in result.variants:
                print(
                    f"     also: {variant['doc_id']} SEC. {variant['section']}"
                    f" ({variant['authority']})"
                )
            print(f"     {' '.join(result.text.split())[:120]}...")
        print("\n* = cited in the answer")

    def set_authority(self, value: str) -> None:
        value = value.strip().lower()
        if value in {"", "all", "none"}:
            self.authority = None
            print("Retrieving from all documents.")
        elif value in {"law", "proposal", "advocacy"}:
            self.authority = value
            print(f"Restricted to authority={value}.")
        else:
            print("Usage: :authority law | proposal | advocacy | all")

    def set_jurisdiction(self, value: str) -> None:
        value = value.strip().lower()
        if value in {"", "all", "none"}:
            self.jurisdiction = None
            print("Retrieving from all jurisdictions.")
        elif value in {"federal", "arizona"}:
            self.jurisdiction = value
            print(f"Restricted to jurisdiction={value}.")
        else:
            print("Usage: :jurisdiction federal | arizona | all")

    def set_k(self, value: str) -> None:
        try:
            self.k = max(1, min(30, int(value)))
            print(f"Retrieving {self.k} chunks per question.")
        except ValueError:
            print("Usage: :k <number>")

    def handle_command(self, line: str) -> bool:
        """Return False to exit."""
        command, _, argument = line[1:].partition(" ")
        match command:
            case "quit" | "q" | "exit":
                return False
            case "help" | "h":
                print(HELP)
            case "sources" | "s":
                self.show_sources()
            case "authority" | "a":
                self.set_authority(argument)
            case "jurisdiction" | "j":
                self.set_jurisdiction(argument)
            case "k":
                self.set_k(argument)
            case "history":
                if not self.history:
                    print("Nothing asked yet.")
                for i, turn in enumerate(self.history, 1):
                    print(f"  {i}. {turn.question}")
            case "clear":
                self.history.clear()
                self.last = None
                print("Conversation cleared.")
            case _:
                print(f"Unknown command {command!r}. Try :help")
        return True

    # -- loop ------------------------------------------------------------------

    def run(self) -> None:
        print(BANNER)
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return

            if not line:
                continue
            if line.startswith(":"):
                if not self.handle_command(line):
                    return
                continue

            answer = self.pipeline.ask(
                line,
                k=self.k,
                history=self.history,
                authority=self.authority,
                jurisdiction=self.jurisdiction,
            )
            self.last = answer
            print()
            print(render(answer))
            print()

            self.history.append(Turn(question=line, answer=answer.text))
            del self.history[:-HISTORY_TURNS]


def main() -> None:
    try:
        shell = Shell()
    except MissingCredentials as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2) from None

    try:
        shell.run()
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
