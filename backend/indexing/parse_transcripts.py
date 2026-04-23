"""Parse transcript .txt files into structured utterances."""
from __future__ import annotations

import json
import re
from pathlib import Path

TRANSCRIPTS_DIR = Path(__file__).parent.parent / "data" / "transcripts"
OUT_PATH = Path(__file__).parent.parent / "data" / "utterances.json"

TIMESTAMP_RE = re.compile(
    r"^(?P<speaker>[^\n(]+?)\s*\((?P<ts>\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\):\s*$",
    re.MULTILINE,
)


def ts_to_seconds(ts: str) -> int:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        h = m = s = 0
    return h * 3600 + m * 60 + s


def parse_one(path: Path) -> list[dict]:
    """Returns a list of utterances: {speaker, ts, seconds, text}."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    matches = list(TIMESTAMP_RE.finditer(text))
    utterances = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        speaker = m.group("speaker").strip()
        ts = m.group("ts")
        utterances.append(
            {
                "speaker": speaker,
                "ts": ts,
                "seconds": ts_to_seconds(ts),
                "text": body,
            }
        )
    return utterances


def main() -> None:
    files = sorted(TRANSCRIPTS_DIR.glob("*.txt"))
    out = {}
    total_utts = 0
    for f in files:
        utts = parse_one(f)
        out[f.stem] = utts
        total_utts += len(utts)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"Parsed {len(files)} files, {total_utts} utterances → {OUT_PATH}")


if __name__ == "__main__":
    main()
