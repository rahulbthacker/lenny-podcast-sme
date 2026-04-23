"""Parse Lenny's Podcast RSS feed → structured episodes.json."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import feedparser
import requests

RSS_URL = "https://api.substack.com/feed/podcast/10845.rss"
OUT_PATH = Path(__file__).parent.parent / "data" / "episodes.json"


def extract_guest_name(title: str) -> str:
    """Episode titles follow the pattern: 'Hook | Guest Name (context)'.
    We return just the guest name stripped of parenthetical context."""
    if "|" in title:
        tail = title.split("|")[-1].strip()
    else:
        tail = title
    tail = re.sub(r"\([^)]*\)", "", tail).strip()
    return tail


def parse_rss() -> list[dict]:
    resp = requests.get(RSS_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)
    episodes = []
    for idx, entry in enumerate(feed.entries):
        title = entry.get("title", "")
        guest = extract_guest_name(title)
        pub_date = entry.get("published", "")
        try:
            dt = datetime(*entry.published_parsed[:6])
            date_iso = dt.strftime("%Y-%m-%d")
        except Exception:
            date_iso = ""
        link = entry.get("link", "")
        summary = entry.get("summary", "")
        summary = re.sub(r"<[^>]+>", " ", summary)
        summary = re.sub(r"\s+", " ", summary).strip()[:500]
        image = ""
        for k in ("image", "itunes_image"):
            if entry.get(k):
                v = entry[k]
                image = v.get("href", "") if isinstance(v, dict) else v
                if image:
                    break
        episodes.append(
            {
                "id": f"ep_{idx:03d}",
                "title": title,
                "guest": guest,
                "date": date_iso,
                "link": link,
                "image": image,
                "summary": summary,
            }
        )
    return episodes


def main() -> None:
    episodes = parse_rss()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(episodes, indent=2))
    print(f"Wrote {len(episodes)} episodes → {OUT_PATH}")


if __name__ == "__main__":
    main()
