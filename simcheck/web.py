"""Local web interface: python -m simcheck.web, then open http://127.0.0.1:8000

Uses only the standard library. It listens on 127.0.0.1, so only this
computer can reach it.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import engine
from .aicheck import ai_check
from .compare import Document, compare_all, shared_passages
from .webcheck import WebCheckError, brave_search, fetch_page_text, web_check

STATIC = Path(__file__).with_name("static")
SAMPLES = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_SETS = {"compare": SAMPLES, "ai": SAMPLES / "ai-check"}

# The Brave Search key comes from the environment, so it is never stored in
# the code, the browser or the repository.
BRAVE_KEY_VAR = "BRAVE_SEARCH_API_KEY"

# Only these files are served, so no request path can reach other files on disk.
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}

MAX_BODY_BYTES = 5 * 1024 * 1024  # refuse uploads bigger than 5 MB
MAX_DOCUMENTS = 50
MAX_PARAM = 50  # upper limit for k and w


class NotConfigured(Exception):
    """A feature needs setup (such as an API key) before it can run."""


def _text_param(payload: object) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or not payload["text"].strip():
        raise ValueError("send a JSON object with a non-empty 'text'")
    return payload["text"]


def _int_param(payload: dict, key: str, default: int) -> int:
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= MAX_PARAM:
        raise ValueError(f"{key} must be a whole number from 1 to {MAX_PARAM}")
    return value


def analyze(payload: object) -> dict:
    """Validate a /api/compare request and return scores plus highlight ranges.

    Ranges are character positions in each document's text, so the page can
    highlight the original text exactly.
    """
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    raw_docs = payload.get("documents")
    if not isinstance(raw_docs, list) or not 2 <= len(raw_docs) <= MAX_DOCUMENTS:
        raise ValueError(f"send between 2 and {MAX_DOCUMENTS} documents")
    for d in raw_docs:
        if not (isinstance(d, dict) and isinstance(d.get("name"), str) and isinstance(d.get("text"), str)):
            raise ValueError("each document needs a text 'name' and 'text'")
    k = _int_param(payload, "k", 5)
    w = _int_param(payload, "w", 4)

    started = time.perf_counter()
    engine_name, impl = engine.resolve("auto")
    docs = [Document.from_text(d["name"], d["text"], impl.fingerprint, k, w) for d in raw_docs]
    index = {id(doc): i for i, doc in enumerate(docs)}

    def ranges(doc: Document, shared: frozenset[int]) -> list[tuple[int, int]]:
        return [doc.char_range(s, e) for s, e in shared_passages(doc, shared, k)]

    pairs = compare_all(docs)
    return {
        "engine": engine_name,
        "k": k,
        "w": w,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "pairs": [
            {
                "a": index[id(m.a)],
                "b": index[id(m.b)],
                "score": m.score,
                "a_in_b": m.a_in_b,
                "b_in_a": m.b_in_a,
                "jaccard": m.jaccard,
                "a_ranges": ranges(m.a, m.shared),
                "b_ranges": ranges(m.b, m.shared),
            }
            for m in pairs
        ],
    }


def ai_check_request(payload: object) -> dict:
    return ai_check(_text_param(payload))


def web_search_configured() -> bool:
    return bool(os.environ.get(BRAVE_KEY_VAR, "").strip())


def web_check_request(payload: object) -> dict:
    text = _text_param(payload)
    if not web_search_configured():
        raise NotConfigured(
            f"Web check needs a Brave Search API key. Set {BRAVE_KEY_VAR} and restart the server "
            "(see 'How it works')."
        )
    engine_name, impl = engine.resolve("auto")
    result = web_check(
        text,
        search=brave_search(os.environ[BRAVE_KEY_VAR].strip()),
        fetch=fetch_page_text,
        fingerprint=impl.fingerprint,
    )
    return {"engine": engine_name, **result}


def load_samples(sample_set: str = "compare") -> list[dict]:
    folder = SAMPLE_SETS.get(sample_set)
    if folder is None:
        raise ValueError(f"unknown sample set {sample_set!r}")
    return [
        {"name": p.name, "text": p.read_text(encoding="utf-8", errors="replace")}
        for p in sorted(folder.glob("*.txt"))
    ]


POST_ROUTES = {
    "/api/compare": analyze,
    "/api/ai-check": ai_check_request,
    "/api/web-check": web_check_request,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "simcheck"

    def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")  # always pick up edited files
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, data: object) -> None:
        self._send(status, json.dumps(data).encode("utf-8"), "application/json")

    def _from_this_computer(self) -> bool:
        # Blocks "DNS rebinding", where a website tricks your browser into
        # calling a local server under the website's own name.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def do_GET(self) -> None:
        if not self._from_this_computer():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
        url = urlsplit(self.path)
        if url.path in STATIC_FILES:
            name, content_type = STATIC_FILES[url.path]
            return self._send(HTTPStatus.OK, (STATIC / name).read_bytes(), content_type)
        if url.path == "/api/samples":
            sample_set = parse_qs(url.query).get("set", ["compare"])[0]
            try:
                return self._json(HTTPStatus.OK, load_samples(sample_set))
            except ValueError as err:
                return self._json(HTTPStatus.NOT_FOUND, {"error": str(err)})
        if url.path == "/api/info":
            name, _ = engine.resolve("auto")
            return self._json(HTTPStatus.OK, {
                "engine": name, "max_documents": MAX_DOCUMENTS, "max_body_bytes": MAX_BODY_BYTES,
                "max_param": MAX_PARAM, "web_search": web_search_configured(),
            })
        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._from_this_computer():
            return self._json(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
        handler = POST_ROUTES.get(urlsplit(self.path).path)
        if handler is None:
            return self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(HTTPStatus.LENGTH_REQUIRED, {"error": "Content-Length required"})
        if not 0 <= length <= MAX_BODY_BYTES:
            return self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request too large (5 MB max)"})
        try:
            result = handler(json.loads(self.rfile.read(length)))
        except NotConfigured as err:
            return self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(err)})
        except WebCheckError as err:
            return self._json(HTTPStatus.BAD_GATEWAY, {"error": str(err)})
        except (ValueError, UnicodeDecodeError) as err:  # JSONDecodeError is a ValueError
            return self._json(HTTPStatus.BAD_REQUEST, {"error": str(err)})
        self._json(HTTPStatus.OK, result)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="simcheck.web", description="Run the simcheck web page locally.")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"simcheck running at http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    print(f"Web check: {'enabled' if web_search_configured() else f'disabled (set {BRAVE_KEY_VAR} to enable)'}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
