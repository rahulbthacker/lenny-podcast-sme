"""Update episode metadata columns in the existing LanceDB table
without re-embedding. Used after re-matching filenames → episodes."""
from __future__ import annotations

import json
from pathlib import Path

import lancedb

DATA = Path(__file__).parent.parent / "data"
INDEX_DIR = DATA / "index"
EPISODES = DATA / "episodes.json"
MATCHES = DATA / "matches.json"


def main() -> None:
    episodes = {ep["id"]: ep for ep in json.loads(EPISODES.read_text())}
    matches = json.loads(MATCHES.read_text())

    db = lancedb.connect(str(INDEX_DIR))
    tbl = db.open_table("chunks")
    rows = tbl.to_arrow().to_pylist()
    print(f"Table has {len(rows)} rows; patching episode metadata...")

    updated = 0
    for row in rows:
        filename = row["filename"]
        match = matches.get(filename)
        if not match:
            continue
        ep = episodes.get(match["episode_id"])
        if not ep:
            continue
        row["episode_id"] = ep["id"]
        row["episode_title"] = ep["title"]
        row["episode_guest"] = ep["guest"]
        row["episode_date"] = ep["date"]
        row["episode_link"] = ep["link"]
        row["episode_image"] = ep["image"]
        updated += 1

    schema = tbl.schema
    db.drop_table("chunks")
    db.create_table("chunks", data=rows, schema=schema)
    print(f"Patched {updated} rows.")


if __name__ == "__main__":
    main()
