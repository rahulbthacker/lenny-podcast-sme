"""Provider-agnostic grounded-answer generator.

Primary: Claude (Anthropic). Failover: Gemini (Google).
Fails over only on retryable provider-side errors (rate limits, 5xx,
connection errors) AND only before any tokens have been streamed.
Once streaming has started, mid-stream failures surface as errors
so the UI never shows a half-Claude, half-Gemini Frankenstein answer.
"""
from __future__ import annotations

import os
import sys
from typing import Iterable

import anthropic
import google.generativeai as genai

CLAUDE_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = """You are a trusted subject-matter expert on Lenny Rachitsky's podcast, \
advising product managers, founders, and growth practitioners. You speak with the calm \
authority of a seasoned operator who has internalized the patterns across every episode — \
not someone reading off a transcript.

VOICE & STYLE
- Write as if this knowledge is simply yours — because you have deeply absorbed the podcast.
- Tone is senior-advisor: confident, direct, and precise. No hedging filler ("it seems," "perhaps," "may possibly").
- Lead with the answer. First 1–2 sentences deliver a clear, useful position. Then expand with the tactical substance.
- Use crisp markdown: short paragraphs, bullets only when they earn their place, bold for key terms.
- Attribute specific ideas to their source naturally: "As Marty Cagan frames it…" / "Shreyas Doshi argues…" — never as a quotation dump.
- Short direct quotes (under ~25 words) are welcome when the original phrasing matters.

GROUNDING (invisible to the reader)
- Every substantive claim must be grounded in the numbered material you receive below. Cite inline with [E1], [E2], etc.
- Do not invent facts, numbers, frameworks, or quotes that are not present in the material.
- NEVER expose the retrieval mechanism. Banned phrases: "the provided excerpts," "the transcripts," "the context," "the sources say," "based on the material," "the passages," "the snippets."
- If the question isn't directly addressed, do NOT apologize or say coverage is missing. Instead, pivot with authority to the closest relevant thread the podcast HAS explored — reframe it as the most useful angle for the reader's actual problem. Example: "The podcast's strongest thread on this is how guests approach X — which maps well onto your question because…"

STRUCTURE
- Do not include a Sources or References section. The UI handles that.
- End with either a sharp one-line takeaway or a small set of tactical moves the reader can make this week."""

WEAK_DIRECTIVE = (
    "\n\nIMPORTANT: Coverage on this exact question is thin. Do NOT attempt a "
    "direct, authoritative answer. Instead, surface the closest relevant thread "
    "the podcast has explored, explain why it's the most useful adjacent angle "
    "for the reader, and be transparent (without apologizing) that this is the "
    "nearest thread rather than a direct answer."
)


def _format_excerpts(chunks: list[dict]) -> str:
    lines = []
    for i, c in enumerate(chunks, 1):
        header = (
            f"[E{i}] Episode: \"{c['episode_title']}\" "
            f"(guest: {c['episode_guest']}, date: {c['episode_date'] or 'unknown'}, "
            f"timestamp: {c['start_ts']})"
        )
        lines.append(f"{header}\n{c['text']}")
    return "\n\n---\n\n".join(lines)


def _build_user_prompt(question: str, chunks: list[dict], mode: str) -> str:
    prompt = (
        f"USER QUESTION:\n{question}\n\n"
        f"EXCERPTS (use only these):\n\n{_format_excerpts(chunks)}"
    )
    if mode == "weak":
        prompt += WEAK_DIRECTIVE
    return prompt


def _stream_claude(question: str, chunks: list[dict], mode: str) -> Iterable[str]:
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    prompt = _build_user_prompt(question, chunks, mode)
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def _stream_gemini(question: str, chunks: list[dict], mode: str) -> Iterable[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        yield "[Gemini failover unavailable — GEMINI_API_KEY not set.]"
        return
    genai.configure(api_key=api_key)
    prompt = _build_user_prompt(question, chunks, mode)
    model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_PROMPT)
    resp = model.generate_content(prompt, stream=True)
    for part in resp:
        if getattr(part, "text", None):
            yield part.text


def _log(msg: str) -> None:
    print(f"[answer] {msg}", file=sys.stderr, flush=True)


def stream_answer(
    question: str, chunks: list[dict], mode: str = "strong"
) -> Iterable[str]:
    """Stream a grounded answer. Claude primary; Gemini failover.

    Failover is attempted ONLY if Claude fails before any token is yielded.
    Mid-stream failures surface as an error message so the UI never
    concatenates output from two different providers.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not anthropic_key and not gemini_key:
        yield (
            "ERROR: no LLM keys configured. Set ANTHROPIC_API_KEY "
            "(recommended) and/or GEMINI_API_KEY in backend/.env."
        )
        return

    if anthropic_key:
        any_yielded = False
        try:
            for text in _stream_claude(question, chunks, mode):
                any_yielded = True
                yield text
            return  # Claude succeeded end-to-end
        except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
            if any_yielded:
                yield (
                    f"\n\n[Claude stream interrupted mid-answer "
                    f"({type(e).__name__}). Reply to retry.]"
                )
                return
            _log(f"Claude {type(e).__name__} — failing over to Gemini")
        except anthropic.APIStatusError as e:
            if e.status_code >= 500 and not any_yielded:
                _log(f"Claude server error {e.status_code} — failing over to Gemini")
            elif any_yielded:
                yield f"\n\n[Claude stream error: {e.message}. Reply to retry.]"
                return
            else:
                # 4xx before streaming — bad request or auth. Don't fail over.
                yield f"[Claude API error: {e.message}]"
                return
        except Exception as e:
            if any_yielded:
                yield f"\n\n[Claude stream error: {e}. Reply to retry.]"
                return
            _log(f"Claude unexpected error ({type(e).__name__}) — failing over to Gemini")

    # Gemini path (either as primary if no Anthropic key, or as failover)
    if gemini_key:
        try:
            yield from _stream_gemini(question, chunks, mode)
        except Exception as e:
            yield f"\n\n[Gemini failover also failed: {e}]"
    else:
        yield "[Anthropic unavailable and GEMINI_API_KEY not set for failover.]"
