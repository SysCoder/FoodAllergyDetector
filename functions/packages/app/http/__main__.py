"""Prototype: run the existing FastAPI app inside an OpenWhisk handler.

The point is that `main.py` is not modified at all. This file is the only
production-specific code, and it is a translation layer, not a second app.
"""
from __future__ import annotations
import asyncio, base64, json
from urllib.parse import urlencode

import os
import sys

# The app modules are staged alongside this file by scripts/stage_functions.sh,
# so the package is self-contained. Locally the same import resolves from the
# repository root, which is what lets this be exercised without deploying.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app  # the SAME FastAPI object uvicorn serves locally

RESERVED = {"http", "__ow_method", "__ow_path", "__ow_headers", "__ow_body"}

# Two independent defences against the closed-loop failure:
#
#   1. Here: one loop for the life of the container, so connection pools
#      survive between warm invocations and are not rebuilt each time.
#   2. In main.py: the SDK client is keyed on the running loop, so if this
#      loop is ever replaced the app builds a fresh client instead of reusing
#      one stranded on a dead loop.
#
# (1) alone is a performance choice that happens to hide the bug. (2) alone is
# correct but rebuilds the pool whenever the loop changes. Together the handler
# is both fast and impossible to strand.
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _loop() -> asyncio.AbstractEventLoop:
    """The container loop, replaced if anything has closed it underneath us."""
    global _LOOP
    if _LOOP.is_closed():
        _LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_LOOP)
    return _LOOP


async def _run(scope, body: bytes) -> dict:
    messages, sent = [], {"body": b"", "status": 500, "headers": []}

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]
            sent["headers"] = message.get("headers", [])
        elif message["type"] == "http.response.body":
            sent["body"] += message.get("body", b"")
        messages.append(message)

    await app(scope, receive, send)
    return sent


def main(event, context=None):
    http = event.get("http", {}) or {}
    method = (http.get("method") or "GET").upper()
    path = http.get("path") or "/"
    headers = {k.lower(): v for k, v in (http.get("headers") or {}).items()}

    # With `web: raw` DigitalOcean base64-encodes the body for binary content
    # types and passes text through as-is, and does not always set a flag. Try
    # the declared encoding first, then fall back on a strict base64 decode,
    # then treat it as text. A JSON body is never valid base64 (it contains
    # braces, quotes and spaces), so the strict attempt cannot misfire on one.
    raw = http.get("body") or ""
    if isinstance(raw, bytes):
        body = raw
    elif http.get("isBase64Encoded"):
        body = base64.b64decode(raw)
    else:
        try:
            body = base64.b64decode(raw, validate=True)
        except Exception:
            body = raw.encode()

    # web: raw puts the unparsed query string on http.queryString. web: true
    # instead merges parsed params into the event, so support both.
    qs = http.get("queryString")
    if qs:
        query_string = qs.encode() if isinstance(qs, str) else qs
    else:
        query_string = urlencode(
            {k: v for k, v in event.items() if k not in RESERVED}
        ).encode()

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.1"},
        "http_version": "1.1", "method": method, "scheme": "https",
        "path": path, "raw_path": path.encode(),
        "query_string": query_string,
        "root_path": "", "client": ("127.0.0.1", 0), "server": ("do", 443),
        "headers": [[k.encode(), str(v).encode()] for k, v in headers.items()],
    }

    result = _loop().run_until_complete(_run(scope, body))
    out_headers = {k.decode(): v.decode() for k, v in result["headers"]}
    text = result["body"].decode("utf-8", "replace")
    return {"statusCode": result["status"], "headers": out_headers, "body": text}
