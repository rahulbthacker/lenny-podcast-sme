"""Lightweight structured logging for /api/chat.

Writes one JSON object per request to backend/logs/chat.jsonl. No PII:
IPs are hashed with a server-side salt, only country-level geo is stored.
Country lookup uses ipapi.co (no signup, generous free tier) with an
in-memory cache so repeat visitors don't cost an API call each request.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "chat.jsonl"

_IP_SALT = os.environ.get("IP_HASH_SALT", "lenny-sme-dev-salt")
_country_cache: dict[str, str] = {}


def hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}{_IP_SALT}".encode()).hexdigest()[:16]


def lookup_country(ip: str) -> str:
    """Return ISO-2 country code for an IP. Cached. Fails soft to '?'."""
    if ip in _country_cache:
        return _country_cache[ip]
    if (
        ip in ("127.0.0.1", "localhost", "::1")
        or ip.startswith("192.168.")
        or ip.startswith("10.")
        or ip.startswith("172.")
    ):
        _country_cache[ip] = "local"
        return "local"
    try:
        resp = requests.get(
            f"https://ipapi.co/{ip}/country/",
            timeout=3,
            headers={"User-Agent": "lenny-sme/1.0"},
        )
        code = resp.text.strip() if resp.status_code == 200 else "?"
        if len(code) != 2:
            code = "?"
    except Exception:
        code = "?"
    _country_cache[ip] = code
    return code


def log_chat_event(event: dict[str, Any]) -> None:
    """Append a JSON-line event. Failures are silent — never break a request."""
    try:
        event.setdefault("t", datetime.now(timezone.utc).isoformat())
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
