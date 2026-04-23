"""Chunk utterances, embed with bge-small-en-v1.5, write to LanceDB."""
from __future__ import annotations

import json
from pathlib import Path

import lancedb
import numpy as np
import pyarrow as pa
from fastembed import TextEmbedding

DATA = Path(__file__).parent.parent / "data"
INDEX_DIR = DATA / "index"
EPISODES = DATA / "episodes.json"
UTTERANCES = DATA / "utterances.json"
MATCHES = DATA / "matches.json"

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384
CHUNK_CHAR_TARGET = 1800
CHUNK_CHAR_MAX = 2600


def group_utterances(utts: list[dict]) -> list[dict]:
    """Group consecutive utterances into ~1800-char chunks that respect turn boundaries."""
    chunks = []
    buf: list[dict] = []
    buf_len = 0
    for u in utts:
        text = u["text"]
        if not text:
            continue
        if buf_len + len(text) > CHUNK_CHAR_MAX and buf:
            chunks.append(_flush(buf))
            buf, buf_len = [], 0
        buf.append(u)
        buf_len += len(text)
        if buf_len >= CHUNK_CHAR_TARGET:
            chunks.append(_flush(buf))
            buf, buf_len = [], 0
    if buf:
        chunks.append(_flush(buf))
    return chunks


def _flush(buf: list[dict]) -> dict:
    text = "\n\n".join(f"{u['speaker']}: {u['text']}" for u in buf)
    return {
        "start_ts": buf[0]["ts"],
        "start_seconds": buf[0]["seconds"],
        "text": text,
    }


def hhmmss(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def build() -> None:
    episodes = {ep["id"]: ep for ep in json.loads(EPISODES.read_text())}
    utterances = json.loads(UTTERANCES.read_text())
    matches = json.loads(MATCHES.read_text())

    all_chunks: list[dict] = []
    for filename, utts in utterances.items():
        match = matches.get(filename)
        ep = episodes.get(match["episode_id"]) if match else None
        chunks = group_utterances(utts)
        for i, c in enumerate(chunks):
            all_chunks.append(
                {
                    "chunk_id": f"{filename}::{i:04d}",
                    "filename": filename,
                    "episode_id": ep["id"] if ep else "",
                    "episode_title": ep["title"] if ep else f"[Unmatched] {filename}",
                    "episode_guest": ep["guest"] if ep else filename,
                    "episode_date": ep["date"] if ep else "",
                    "episode_link": ep["link"] if ep else "",
                    "episode_image": ep["image"] if ep else "",
                    "start_ts": c["start_ts"],
                    "start_seconds": c["start_seconds"],
                    "text": c["text"],
                }
            )

    print(f"Prepared {len(all_chunks)} chunks from {len(utterances)} transcripts.")
    print(f"Loading embedding model: {MODEL_NAME} (first run downloads ~130MB)...")
    model = TextEmbedding(model_name=MODEL_NAME)
    texts = [c["text"] for c in all_chunks]
    print(f"Encoding {len(texts)} chunks (this takes a few minutes)...")
    vectors = []
    for i, vec in enumerate(model.embed(texts, batch_size=64)):
        vectors.append(np.asarray(vec, dtype=np.float32))
        if (i + 1) % 200 == 0:
            print(f"  embedded {i + 1}/{len(texts)}")

    for c, v in zip(all_chunks, vectors):
        c["vector"] = v.tolist()

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(INDEX_DIR))
    if "chunks" in db.table_names():
        db.drop_table("chunks")

    schema = pa.schema(
        [
            pa.field("chunk_id", pa.string()),
            pa.field("filename", pa.string()),
            pa.field("episode_id", pa.string()),
            pa.field("episode_title", pa.string()),
            pa.field("episode_guest", pa.string()),
            pa.field("episode_date", pa.string()),
            pa.field("episode_link", pa.string()),
            pa.field("episode_image", pa.string()),
            pa.field("start_ts", pa.string()),
            pa.field("start_seconds", pa.int32()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), EMBED_DIM)),
        ]
    )
    tbl = db.create_table("chunks", schema=schema)
    tbl.add(all_chunks)
    print(f"Wrote {len(all_chunks)} chunks to LanceDB at {INDEX_DIR}")


if __name__ == "__main__":
    build()
