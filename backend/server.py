"""FastAPI server: /api/chat (SSE streaming) + /api/health."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv(Path(__file__).parent / ".env")

from answer import stream_answer  # noqa: E402
from logging_utils import hash_ip, log_chat_event, lookup_country  # noqa: E402
from retrieval import Retriever  # noqa: E402

app = FastAPI(title="Lenny Podcast SME")

# CORS — comma-separated origins in env var, defaults to permissive for local dev.
_cors_env = os.environ.get("CORS_ORIGINS", "*")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Per-IP rate limit. Applies to /api/chat only.
#
# Key function details:
# - Prefers `X-Forwarded-For` so that behind a proxy (Railway, Vercel, Cloudflare)
#   we rate-limit real client IPs, not the proxy itself.
# - Returns a unique key per request for LOOPBACK IPs — this means local
#   development and testing (127.0.0.1, ::1) never accumulate against the
#   daily limit. Production traffic (any public IP) is limited normally.
# In a multi-process deploy, swap storage_uri for Redis so the counter is shared.
def _rate_limit_key(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    ip = xff.split(",")[0].strip() if xff else get_remote_address(request)
    if ip in ("", "127.0.0.1", "::1", "localhost"):
        return f"local:{time.time_ns()}"
    return ip


limiter = Limiter(key_func=_rate_limit_key, default_limits=[])
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(int(retry_after))} if retry_after else {}
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit",
            "message": (
                "You've hit the daily request limit for this demo "
                "(30 per day). Try again tomorrow."
            ),
        },
        headers=headers,
    )

retriever: Retriever | None = None


def get_retriever() -> Retriever:
    global retriever
    if retriever is None:
        retriever = Retriever()
    return retriever


class ChatRequest(BaseModel):
    question: str
    k: int = 8


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "anthropic_key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY")),
    }


OUT_OF_SCOPE_SUGGESTIONS = [
    "How do I transition into product management from engineering?",
    "What's the best way to run a kickoff for a new PM team?",
    "How should an early-stage startup think about pricing?",
    "How is AI changing the product manager role?",
]


@app.post("/api/chat")
@limiter.limit("30/day")
def chat(request: Request, req: ChatRequest) -> StreamingResponse:
    started = time.time()
    client_ip = get_remote_address(request)
    r = get_retriever()
    chunks = r.search(req.question, k=req.k)
    scope = r.classify_scope(req.question, chunks)

    # Mutable counters that the streaming generator updates; logged after completion.
    stats = {"out_chars": 0}

    def event_stream():
        try:
            if scope["mode"] == "out_of_scope":
                if scope["domain_sim"] < 0.50:
                    message = (
                        "That's outside what Lenny's guests have explored. "
                        "This assistant is focused on product management, growth, "
                        "startup building, and PM career topics. Try one of the "
                        "prompts below — or ask your own question in that space."
                    )
                else:
                    message = (
                        "This one is in the neighborhood of what the podcast covers, "
                        "but I couldn't find a strong thread on it specifically. "
                        "Try one of the adjacent prompts below, or rephrase what "
                        "you're trying to learn."
                    )
                yield json.dumps(
                    {
                        "type": "out_of_scope",
                        "data": {
                            "message": message,
                            "suggestions": OUT_OF_SCOPE_SUGGESTIONS,
                        },
                    }
                ) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
                return

            yield json.dumps({"type": "citations", "data": chunks}) + "\n"
            for piece in stream_answer(req.question, chunks, mode=scope["mode"]):
                if piece:
                    stats["out_chars"] += len(piece)
                    yield json.dumps({"type": "token", "data": piece}) + "\n"
            yield json.dumps({"type": "done"}) + "\n"
        finally:
            # Runs whether the stream completed or the client disconnected.
            log_chat_event(
                {
                    "ip_hash": hash_ip(client_ip),
                    "country": lookup_country(client_ip),
                    "q": req.question,
                    "mode": scope["mode"],
                    "cites": len(chunks) if scope["mode"] != "out_of_scope" else 0,
                    "top_distance": round(scope.get("top_distance", 0.0), 3),
                    "domain_sim": round(scope.get("domain_sim", 0.0), 3),
                    "out_chars": stats["out_chars"],
                    "latency_ms": int((time.time() - started) * 1000),
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8787, reload=False)
