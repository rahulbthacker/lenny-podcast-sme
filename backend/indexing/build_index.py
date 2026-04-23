"""Orchestrator: run the full indexing pipeline."""
from indexing import parse_rss, parse_transcripts, match, chunk_and_embed


def main() -> None:
    print("\n== Step 1: parsing RSS ==")
    parse_rss.main()
    print("\n== Step 2: parsing transcripts ==")
    parse_transcripts.main()
    print("\n== Step 3: matching filenames to episodes ==")
    match.match_all()
    print("\n== Step 4: chunking + embedding + indexing ==")
    chunk_and_embed.build()
    print("\nDone.")


if __name__ == "__main__":
    main()
