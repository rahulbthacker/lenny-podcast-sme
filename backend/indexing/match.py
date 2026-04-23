"""Match transcript filenames to RSS episodes.

Scoring combines title + slug + guest fuzzy matches, with a strong bonus
for exact token-set match against the URL slug. Global greedy bipartite
assignment enforces the one-episode-per-filename constraint.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from rapidfuzz import fuzz

DATA = Path(__file__).parent.parent / "data"
EPISODES = DATA / "episodes.json"
UTTERANCES = DATA / "utterances.json"
OUT = DATA / "matches.json"

MIN_SCORE = 55.0  # drop-below-this counts as unmatched


def clean_filename(name: str) -> str:
    """Strip trivial punctuation only. Preserves distinctive tokens like
    'Live' and '2.0' — those are the discriminators for repeat appearances."""
    n = name.replace("_", " ").strip()
    return re.sub(r"\s+", " ", n)


def slug_from_link(link: str) -> str:
    if "/p/" in link:
        return link.split("/p/", 1)[1].split("?")[0].rstrip("/")
    return ""


def _guest_is_namelike(guest: str) -> bool:
    parts = re.findall(r"[A-Za-z]+", guest)
    if not (2 <= len(parts) <= 4):
        return False
    return all(p[0].isupper() for p in parts if p)


def score_episode(clean_fn: str, ep: dict) -> float:
    title = ep.get("title", "")
    slug = slug_from_link(ep.get("link", ""))
    slug_text = slug.replace("-", " ")
    guest = ep.get("guest", "")

    # partial_ratio — detects the filename as a substring of a longer
    # title/slug/guest. Handles short filenames ("Boz") against long titles
    # correctly; token_set_ratio would punish them for length mismatch.
    cf = clean_fn.lower()
    title_score = fuzz.partial_ratio(cf, title.lower())
    slug_score = fuzz.partial_ratio(cf, slug_text.lower())
    guest_score = fuzz.WRatio(clean_fn, guest) if _guest_is_namelike(guest) else 0.0

    # Max of three independent signals — each can confirm a match on its own.
    # Add a 20% slug-score contribution on top as a per-episode tiebreaker
    # (slug is the most specific per-episode identifier in the feed).
    base = max(title_score, slug_score, guest_score) + 0.2 * slug_score

    # Token-set bonus against slug — the cleanest per-episode discriminator.
    fn_tokens = {w.lower() for w in clean_fn.split() if w.strip()}
    slug_tokens = {w.lower() for w in slug_text.split() if w.strip()}
    if fn_tokens and slug_tokens:
        if fn_tokens == slug_tokens:
            base += 25.0
        elif fn_tokens <= slug_tokens:
            base += 8.0
        elif slug_tokens < fn_tokens:
            base += 3.0  # slug is a subset of filename — weaker but still a signal

    return base


def match_all() -> dict:
    episodes = json.loads(EPISODES.read_text())
    utterances = json.loads(UTTERANCES.read_text())
    filenames = list(utterances.keys())
    id_to_ep = {ep["id"]: ep for ep in episodes}

    # Build (score, filename, episode_id) triples for greedy assignment.
    triples: list[tuple[float, str, str]] = []
    for fn in filenames:
        cleaned = clean_filename(fn)
        for ep in episodes:
            s = score_episode(cleaned, ep)
            triples.append((s, fn, ep["id"]))

    # Sort by score descending, with stable tiebreaker on filename + episode ID
    # so behavior is deterministic across runs.
    triples.sort(key=lambda t: (-t[0], t[1], t[2]))

    matches: dict[str, dict | None] = {fn: None for fn in filenames}
    claimed_ep_ids: set[str] = set()
    for score, fn, ep_id in triples:
        if score < MIN_SCORE:
            break
        if matches[fn] is not None:
            continue
        if ep_id in claimed_ep_ids:
            continue
        matches[fn] = {
            "episode_id": ep_id,
            "score": round(score, 2),
            "via": "combined",
        }
        claimed_ep_ids.add(ep_id)

    OUT.write_text(json.dumps(matches, indent=2))

    matched_count = sum(1 for v in matches.values() if v)
    print(f"Matched {matched_count} / {len(filenames)} filenames.")
    unmatched = [fn for fn, v in matches.items() if v is None]
    if unmatched:
        print(f"Unmatched ({len(unmatched)}): {unmatched[:20]}")

    # Sanity: any two filenames mapped to the same episode? (Should be none.)
    seen: dict[str, str] = {}
    dupes = []
    for fn, v in matches.items():
        if not v:
            continue
        ep_id = v["episode_id"]
        if ep_id in seen:
            dupes.append((seen[ep_id], fn, ep_id))
        else:
            seen[ep_id] = fn
    if dupes:
        print(f"WARNING: {len(dupes)} duplicate episode assignments:")
        for a, b, ep_id in dupes:
            title = id_to_ep[ep_id]["title"][:60]
            print(f"  - {a!r} and {b!r} → {ep_id} ({title})")
    return matches


if __name__ == "__main__":
    match_all()
