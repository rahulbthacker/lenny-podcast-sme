"""Vector retrieval over the LanceDB chunks table, with scope classification."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

import lancedb
import numpy as np
from fastembed import TextEmbedding

DATA = Path(__file__).parent / "data"
INDEX_DIR = DATA / "index"
EPISODES_PATH = DATA / "episodes.json"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Topic anchors — canonical in-scope descriptions used to detect off-domain
# queries independently of whether matching transcripts exist.
TOPIC_ANCHORS = [
    "Product management roles, frameworks, decisions, and team dynamics",
    "Product-market fit, product discovery, and product strategy",
    "Growth loops, user acquisition, activation, retention, and monetization",
    "Startup founding, fundraising, go-to-market, and scaling a company",
    "Product manager career — transitions, interviews, leveling, promotions, compensation",
    "Leadership, influence, communication, and stakeholder management for product people",
    "Building, launching, and iterating on software products",
    "AI, automation, and how they change the product management craft",
    # Navigation / meta-queries about the podcast itself
    "Finding, searching, or navigating to specific episodes of Lenny's podcast",
    "Looking up episode links, guests, titles, dates, and timestamps in the podcast",
    "Asking which episode discusses a topic, or which guest appeared on which episode",
]

# Thresholds (calibrated separately; tuned conservatively for BGE-small).
# LanceDB returns L2 distance on normalized vectors: dist = sqrt(2 * (1 - cos_sim)).
STRONG_MAX_DISTANCE = 0.80   # top-chunk distance below this = solid match
WEAK_MAX_DISTANCE = 1.10     # top-chunk distance above this = no useful chunks
DOMAIN_MIN_COSINE = 0.50     # query-to-topic max cosine below this = off-domain
GUEST_BOOST = 0.30           # distance reduction for chunks whose guest is named
MAX_CHUNKS_PER_EPISODE = 1   # one card per unique episode — no duplicate-episode cards
RELEVANCE_GAP = 0.22         # drop chunks whose adjusted distance is > top + this
ABS_MAX_DISTANCE = 1.20      # never include a chunk above this raw distance


def _bge_query_prefix(q: str) -> str:
    return f"Represent this sentence for searching relevant passages: {q}"


# Common English structural words that must never appear inside a
# name bigram. Short list of function words, pronouns, and podcast jargon.
_STRUCTURE_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to",
    "for", "from", "with", "by", "as", "is", "be", "was", "are", "were",
    "has", "have", "had", "do", "does", "did", "will", "would", "can",
    "could", "should", "may", "might", "must",
    "i", "me", "my", "mine", "you", "your", "yours", "he", "him", "his",
    "she", "her", "hers", "it", "its", "we", "us", "our", "ours", "they",
    "them", "their", "this", "that", "these", "those",
    # Tech/business acronyms common in podcast titles
    "ai", "pm", "ui", "ux", "vp", "ceo", "cto", "cpo", "coo", "cmo",
    "api", "sdk", "app", "ios", "seo", "llm", "rag",
    # Podcast vocabulary
    "live", "podcast", "episode", "part", "edition", "interview",
    # Question words / connectives
    "who", "what", "when", "where", "why", "how", "which", "whose",
    "also", "only", "just", "still", "then", "than",
    # Common product/growth terms that form bigrams with real words
    "product", "growth", "strategy", "team", "teams", "startup",
    "startups", "company", "founder", "founders", "business", "career",
    "leadership", "management", "design", "pricing", "marketing",
    # VC / company-structure words that form spurious "surname" bigrams
    "ventures", "capital", "partners", "labs", "group", "holdings",
    "corp", "inc", "llc", "ltd", "co",
    # Generic podcast-language nouns that sneak in as capitalized title words
    "lessons", "lesson", "story", "stories", "tips", "guide", "guides",
    "playbook", "plays", "tactics", "builders", "operators", "skills",
    "rules", "tools", "secrets", "wisdom", "insights", "tips",
}

# Short English words that happen to be real surnames — when these appear
# alone in a query, we can't tell if they're the surname or the word. We
# still ALLOW them as part of a bigram (so "Megan Cook" matches), but we
# don't allow single-token queries on them to trigger the guest filter.
_AMBIGUOUS_LAST_NAMES = {
    "cook", "grant", "bell", "price", "adams", "fields", "field",
    "black", "white", "brown", "green", "small", "young", "king",
    "valley", "group", "cross", "hill", "mills", "woods", "long",
    "short", "rich", "poor", "hall", "bright", "strong", "wise",
    "love", "chat", "linked", "verna",
    # Domain words that sneak into bigrams as title-cased words
    "ventures", "labs", "partner", "partners", "search", "head",
    "lesson", "lessons", "plays", "playbook", "story", "stories",
    "builder", "builders", "operator", "operators",
}


def _strip_diacritics(text: str) -> str:
    """Remove combining marks but preserve base letter casing."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _normalize(text: str) -> str:
    """Lowercase + strip diacritics — lets 'Söderström' match 'soderstrom'."""
    return _strip_diacritics(text).lower()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]+", _normalize(text))


def _bigrams(toks: list[str]) -> set[tuple[str, str]]:
    return {(toks[i], toks[i + 1]) for i in range(len(toks) - 1)}


def _build_guest_index() -> tuple[set[tuple[str, str]], set[str]]:
    """Extract guest names from episodes.json using three complementary sources.

    Returns:
        pairs: set of (first, last) tuples — full-name matches always trigger
        safe_lasts: set of last names safe for single-token query matching
                    (len ≥ 5 and not in the ambiguous-English-word blocklist)

    Three extraction sources (their union):
    1. `guest` field when it's a clean 2–4-word capitalized name
       (post-pipe guest extraction in the RSS parser).
    2. **Title-Slug bigram intersection** — 2-token sequences that appear
       in both the (normalized) title and the slug. This is the most
       robust source because names reliably appear in both, regardless
       of position within the title.
    3. Title scan for 2-capitalized-word sequences at the start or right
       after a pipe. Handles titles whose slugs truncate the last name
       (e.g. 'product-management-theater-marty' only has "marty" but
       the title has "Marty Cagan").
    """
    try:
        episodes = json.loads(EPISODES_PATH.read_text())
    except FileNotFoundError:
        return set(), set()

    pairs: set[tuple[str, str]] = set()

    def try_add(first: str, last: str) -> None:
        if len(first) < 2 or len(last) < 2:
            return
        if first in _STRUCTURE_STOPWORDS or last in _STRUCTURE_STOPWORDS:
            return
        if first.isdigit() or last.isdigit():
            return
        pairs.add((first, last))

    for ep in episodes:
        guest = ep.get("guest") or ""
        title = ep.get("title") or ""
        link = ep.get("link") or ""
        slug = link.split("/p/", 1)[1].split("?")[0] if "/p/" in link else ""

        # --- Source 1: clean guest field (2–4 capitalized words) ---
        guest_ascii = _normalize(guest)
        gparts_norm = re.findall(r"[a-z]+", guest_ascii)
        # Require original guest to be title-cased in each word
        orig_words = re.findall(r"\S+", guest)
        cap_count = sum(
            1 for w in orig_words if w and w[0:1].isalpha() and w[0:1].isupper()
        )
        if 2 <= len(gparts_norm) <= 4 and cap_count >= len(gparts_norm):
            try_add(gparts_norm[0], gparts_norm[-1])

        # Replace punctuation with spaces so apostrophes/parens don't block
        # the capitalized-pair regex (e.g. "Andrew 'Boz' Bosworth (CTO)").
        title_ascii = re.sub(
            r"\s+", " ", re.sub(r"[^\w\s]", " ", _strip_diacritics(title))
        )

        # --- Source 2: title-slug bigram intersection, capitalized-pair check ---
        # Each candidate (a, b) is added ONLY if the cleaned title contains
        # a contiguous "Capitalized Capitalized" sequence. Filters domain
        # words like "theater marty" or "figma builds" that appear in the
        # slug but aren't proper nouns in the title.
        title_bg = _bigrams(_tokens(title))
        slug_bg = _bigrams(_tokens(slug.replace("-", " ")))
        for a, b in title_bg & slug_bg:
            pat = rf"\b{a.capitalize()}\s+{b.capitalize()}\b"
            if not re.search(pat, title_ascii):
                continue
            try_add(a, b)

        # --- Source 3: title-only 2-capitalized-word patterns.
        # Handles cases where the slug truncates the last name (e.g. slug
        # ends in "...-marty" but title has "Marty Cagan").
        for m in re.finditer(r"\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b", title_ascii):
            try_add(_normalize(m.group(1)), _normalize(m.group(2)))

    # Safe single-token surnames: length ≥5 and not an ambiguous English word
    safe_lasts = {
        last for (_, last) in pairs
        if len(last) >= 5 and last not in _AMBIGUOUS_LAST_NAMES
    }

    return pairs, safe_lasts


class Retriever:
    def __init__(self) -> None:
        self.model = TextEmbedding(model_name=MODEL_NAME)
        db = lancedb.connect(str(INDEX_DIR))
        self.tbl = db.open_table("chunks")
        # Pre-compute topic anchor embeddings once at startup.
        # For topic similarity we embed the raw text (not the BGE query prefix).
        anchor_vecs = list(self.model.embed(TOPIC_ANCHORS))
        self.topic_vecs = np.vstack(
            [np.asarray(v, dtype=np.float32) for v in anchor_vecs]
        )
        self.guest_pairs, self.safe_lasts = _build_guest_index()
        # Flat set of all last names (for quick membership checks during boost).
        self._all_lasts = {last for (_, last) in self.guest_pairs}

    def _mentions_guest(self, query: str) -> bool:
        return bool(self._detect_guest_surnames(query))

    def _detect_guest_surnames(self, query: str) -> set[str]:
        """Surnames matched by a guest mentioned in the query.

        Match modes (both contribute to the returned set):
          - Bigram: (first, last) pair from the query matches a known
            (first, last) pair in `guest_pairs` — catches full-name mentions
            like 'Claire Vo' or 'Ben Horowitz' regardless of surname length.
          - Single-token: a query token matches a surname in `safe_lasts`
            (length ≥ 5 AND not an ambiguous English word) — catches
            surname-only mentions like 'Doshi', 'Cagan', 'Rachitsky'.
        """
        q_toks = _tokens(query)
        matched: set[str] = set()
        # Bigram match
        for i in range(len(q_toks) - 1):
            pair = (q_toks[i], q_toks[i + 1])
            if pair in self.guest_pairs:
                matched.add(pair[1])
        # Single-token fallback on safe surnames
        for tok in q_toks:
            if tok in self.safe_lasts:
                matched.add(tok)
        return matched

    def _embed_query(self, query: str) -> np.ndarray:
        qtext = _bge_query_prefix(query)
        return np.asarray(
            next(iter(self.model.query_embed([qtext]))), dtype=np.float32
        )

    def _embed_raw(self, query: str) -> np.ndarray:
        return np.asarray(next(iter(self.model.embed([query]))), dtype=np.float32)

    def search(self, query: str, k: int = 8) -> list[dict[str, Any]]:
        """Retrieve top-k chunks with two re-ranking passes:

        1. **Guest boost** — if the query names a known guest, chunks from
           that guest's episodes get a fixed distance reduction. This
           surfaces all episodes by that guest (not just the one with the
           best content match), which is essential for navigation-style
           queries ("links to Shreyas episodes").
        2. **Diversity cap** — no single episode contributes more than
           MAX_CHUNKS_PER_EPISODE chunks to the final result. Prevents
           one episode from monopolizing citations and keeps the
           Sources grid informative.
        """
        vec = self._embed_query(query)
        # Over-fetch to give the re-rankers headroom. k*4 is plenty.
        raw = self.tbl.search(vec).limit(k * 4).to_list()

        mentioned = self._detect_guest_surnames(query)

        # Supplementary guest-filtered retrieval: when a guest is named,
        # also fetch the top-ranking chunks RESTRICTED to their episodes.
        # This guarantees the guest's episodes are in the re-rank pool
        # even when the query text is lexically far from their content.
        if mentioned:
            # Tokens are derived from episodes.json (trusted), safe to inline.
            clauses = [
                f"LOWER(episode_title) LIKE '%{tok}%'" for tok in mentioned
            ]
            filter_sql = " OR ".join(clauses)
            try:
                extra = (
                    self.tbl.search(vec).where(filter_sql).limit(k * 2).to_list()
                )
                seen = {r["chunk_id"] for r in raw}
                raw.extend(r for r in extra if r["chunk_id"] not in seen)
            except Exception:
                pass  # fallback to unfiltered results if LanceDB where fails

        # Build candidate list with (possibly boosted) score. Filter out
        # chunks without proper episode metadata (unmatched transcripts).
        candidates: list[dict[str, Any]] = []
        for r in raw:
            if not r.get("episode_link") or not r.get("episode_id"):
                continue
            distance = float(r.get("_distance", 0.0))
            if mentioned:
                # Match against both guest and title — post-pipe guest extraction
                # can lose the name (e.g. "Former PM leader…" for the Shreyas
                # Live episode); title reliably contains the actual guest name.
                match_text = (
                    (r.get("episode_guest") or "")
                    + " "
                    + (r.get("episode_title") or "")
                ).lower()
                if any(tok in match_text for tok in mentioned):
                    distance = max(0.0, distance - GUEST_BOOST)
            candidates.append(
                {
                    "chunk_id": r["chunk_id"],
                    "episode_id": r["episode_id"],
                    "episode_title": r["episode_title"],
                    "episode_guest": r["episode_guest"],
                    "episode_date": r["episode_date"],
                    "episode_link": r["episode_link"],
                    "episode_image": r["episode_image"],
                    "start_ts": r["start_ts"],
                    "start_seconds": int(r["start_seconds"]),
                    "text": r["text"],
                    "score": distance,
                }
            )

        # Re-sort by adjusted distance (lower = better after boost).
        candidates.sort(key=lambda c: c["score"])

        # Apply per-episode cap greedily; collect up to k candidates.
        per_episode: dict[str, int] = {}
        diverse: list[dict[str, Any]] = []
        for c in candidates:
            ep_id = c["episode_id"]
            if per_episode.get(ep_id, 0) >= MAX_CHUNKS_PER_EPISODE:
                continue
            diverse.append(c)
            per_episode[ep_id] = per_episode.get(ep_id, 0) + 1
            if len(diverse) >= k:
                break

        # Relevance-only trimming: always keep the top chunk, then include
        # additional chunks only if they're within RELEVANCE_GAP of the top
        # chunk's adjusted distance AND under the absolute distance ceiling.
        # No minimum-card floor — if only one chunk is relevant, we show one.
        if not diverse:
            return diverse
        top_dist = diverse[0]["score"]
        out: list[dict[str, Any]] = [diverse[0]]
        for c in diverse[1:]:
            if c["score"] - top_dist > RELEVANCE_GAP:
                break
            if c["score"] > ABS_MAX_DISTANCE:
                break
            out.append(c)
        return out

    def domain_similarity(self, query: str) -> float:
        """Max cosine similarity between the query and any topic anchor."""
        q = self._embed_raw(query)
        sims = self.topic_vecs @ q  # anchors are already normalized
        return float(sims.max())

    def classify_scope(
        self, query: str, chunks: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Return {mode, top_distance, domain_sim, reason}.

        Modes:
          strong       — direct answer with citations
          weak         — in-domain but thin coverage; Gemini pivots gracefully
          out_of_scope — off-domain or irrelevant; skip Gemini, show redirect
        """
        top_d = chunks[0]["score"] if chunks else 9.99
        domain_sim = self.domain_similarity(query)
        mentions_guest = self._mentions_guest(query)

        # Guest-name bypass — if the query names a known guest, it's a
        # navigational query about the podcast; skip the domain gate.
        # Domain gate first — rules out off-topic queries even when a random
        # chunk happens to be close in embedding space.
        if not mentions_guest and domain_sim < DOMAIN_MIN_COSINE:
            return {
                "mode": "out_of_scope",
                "top_distance": top_d,
                "domain_sim": domain_sim,
                "reason": "query is off-domain",
            }
        if top_d <= STRONG_MAX_DISTANCE:
            return {
                "mode": "strong",
                "top_distance": top_d,
                "domain_sim": domain_sim,
                "reason": "in-domain and top chunk is a strong match",
            }
        if top_d > WEAK_MAX_DISTANCE:
            return {
                "mode": "out_of_scope",
                "top_distance": top_d,
                "domain_sim": domain_sim,
                "reason": "in-domain but no useful chunks retrieved",
            }
        return {
            "mode": "weak",
            "top_distance": top_d,
            "domain_sim": domain_sim,
            "reason": "in-domain but thin coverage",
        }
