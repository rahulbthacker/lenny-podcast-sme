"""Calibration probe — prints top-1 distance and domain similarity for a
set of known in-scope and out-of-scope queries so the scope thresholds
can be validated or tuned."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from retrieval import Retriever  # noqa: E402

IN_SCOPE = [
    "What's the best way to run a kickoff for a new PM team?",
    "How do I transition into product management from engineering?",
    "How should a startup think about pricing?",
    "What separates great PMs from good ones?",
    "How is AI changing the product manager role?",
    "What does Marty Cagan say about product strategy?",
]

BORDERLINE = [
    "What are PM salary trends right now?",
    "How do I deal with an annoying coworker?",
    "How do I prepare for a product leader interview?",
]

OUT_OF_SCOPE = [
    "What's the weather in Tokyo today?",
    "How do I cook risotto?",
    "Explain quantum entanglement to a 10-year-old",
    "What's a good recipe for banana bread?",
    "Who won the Super Bowl in 2024?",
]


def probe(retriever: Retriever, queries: list[str], label: str) -> None:
    print(f"\n== {label} ==")
    print(f"{'top_d':>6}  {'dom_sim':>7}  {'mode':<12}  query")
    print("-" * 78)
    for q in queries:
        chunks = retriever.search(q, k=3)
        scope = retriever.classify_scope(q, chunks)
        print(
            f"{scope['top_distance']:6.3f}  {scope['domain_sim']:7.3f}  "
            f"{scope['mode']:<12}  {q}"
        )


def main() -> None:
    r = Retriever()
    probe(r, IN_SCOPE, "IN-SCOPE (should be strong)")
    probe(r, BORDERLINE, "BORDERLINE (strong or weak OK)")
    probe(r, OUT_OF_SCOPE, "OUT-OF-SCOPE (should be out_of_scope)")


if __name__ == "__main__":
    main()
