"""Find web pages that contain passages from a document.

1. Pick a few distinctive phrases from the document.
2. Search for each one as an exact quote (Brave Search API).
3. Download the pages that come back and extract their text.
4. Fingerprint each page and compare it with the document.

Only pages the search engine returns for those phrases are checked, so a
low result means "nothing found", not "definitely original".
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from typing import Callable

from .compare import Document, FingerprintFn, compare, shared_passages
from .sentences import split_sentences, words

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
USER_AGENT = "simcheck/0.1 (local document similarity checker)"
TIMEOUT_SECONDS = 10
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_QUERIES = 8
WORDS_PER_QUERY = 14
MAX_PAGES = 12
SEARCH_PAUSE_SECONDS = 1.1  # Brave's free plan allows about one request per second

_COMMON = frozenset(
    "about after again also because been before being between both could does doing during each "
    "every from have having here into just more most much must only other over same should some "
    "such than that their them then there these they this those through under until very what when "
    "where which while will with would your".split()
)

SearchFn = Callable[[str], list[dict]]
FetchFn = Callable[[str], str]


class WebCheckError(Exception):
    """An expected failure with a message that is safe to show the user."""


# ---------------------------------------------------------------- queries

def pick_queries(text: str, max_queries: int = MAX_QUERIES, words_per_query: int = WORDS_PER_QUERY) -> list[str]:
    """Choose distinctive phrases spread across the document, as quoted searches.

    Each candidate is the first `words_per_query` words of a long sentence.
    Candidates with more long, uncommon words are more likely to be unique,
    so the best candidate from each part of the document is used.
    """
    candidates = []
    for start, end in split_sentences(text):
        sentence_words = words(text[start:end])
        if len(sentence_words) < 10:
            continue
        chunk = sentence_words[:words_per_query]
        rarity = sum(1 for w in chunk if len(w) >= 6 and w.lower() not in _COMMON)
        candidates.append((rarity, " ".join(chunk)))
    if not candidates:
        return []
    n = min(max_queries, len(candidates))
    picks = []
    for i in range(n):  # one pick per equal-sized part of the document
        part = candidates[i * len(candidates) // n:(i + 1) * len(candidates) // n]
        picks.append(max(part, key=lambda c: c[0])[1])
    return [f'"{p}"' for p in picks]


# ---------------------------------------------------------------- search

def brave_search(api_key: str) -> SearchFn:
    """Return a search function that queries the Brave Search API."""

    def search(query: str) -> list[dict]:
        url = f"{BRAVE_URL}?{urllib.parse.urlencode({'q': query, 'count': 5})}"
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
            "User-Agent": USER_AGENT,
        })
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                data = json.load(response)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403, 422):
                raise WebCheckError("Brave Search rejected the API key. Check BRAVE_SEARCH_API_KEY.") from None
            if err.code == 429:
                raise WebCheckError("Brave Search rate limit or monthly credit reached. Try again later.") from None
            raise WebCheckError(f"Brave Search returned an error (HTTP {err.code}).") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            raise WebCheckError(f"Couldn't reach Brave Search ({type(err).__name__}).") from None
        results = data.get("web", {}).get("results", []) if isinstance(data, dict) else []
        return [
            {"url": r["url"], "title": str(r.get("title", ""))}
            for r in results
            if isinstance(r, dict) and isinstance(r.get("url"), str) and r["url"].startswith(("http://", "https://"))
        ]

    return search


# ---------------------------------------------------------------- safe fetching

def check_public_url(url: str) -> None:
    """Refuse anything but http(s) URLs whose host resolves only to public addresses.

    Pages come from search results, which we don't control. Without this
    check, a result could point at a router admin page or another service on
    your own network ("server-side request forgery").
    """
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise WebCheckError("not an http(s) address")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except (socket.gaierror, UnicodeError):
        raise WebCheckError("address could not be resolved") from None
    for info in infos:
        if not ipaddress.ip_address(info[4][0].split("%")[0]).is_global:
            raise WebCheckError("refused a private or local network address")


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)  # every hop must be public too
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_CheckedRedirects)


class _TextExtractor(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "template", "svg", "head", "nav", "footer", "form"})
    BLOCK = frozenset({"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts)


def fetch_page_text(url: str) -> str:
    """Download a public web page (max 2 MB) and return its readable text."""
    check_public_url(url)
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9",
    })
    with _opener.open(request, timeout=TIMEOUT_SECONDS) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "application/xhtml+xml", "text/plain"):
            raise WebCheckError(f"skipped {content_type} content")
        raw = response.read(MAX_PAGE_BYTES)
        charset = response.headers.get_content_charset() or "utf-8"
    try:
        page = raw.decode(charset, errors="replace")
    except LookupError:  # unknown charset name
        page = raw.decode("utf-8", errors="replace")
    return page if content_type == "text/plain" else html_to_text(page)


# ---------------------------------------------------------------- the check

def web_check(
    text: str,
    *,
    search: SearchFn,
    fetch: FetchFn,
    fingerprint: FingerprintFn,
    k: int = 5,
    w: int = 4,
    pause: float = SEARCH_PAUSE_SECONDS,
) -> dict:
    started = time.perf_counter()
    queries = pick_queries(text)
    if not queries:
        raise WebCheckError("The document needs at least one sentence of 10+ words to search for.")

    # url -> {"title", "hits"}; insertion order keeps the search ranking.
    found: dict[str, dict] = {}
    searched = []
    for i, query in enumerate(queries):
        if i and pause:
            time.sleep(pause)
        results = search(query)  # WebCheckError (bad key, rate limit) stops the whole check
        searched.append({"query": query, "results": len(results)})
        for result in results:
            entry = found.setdefault(result["url"], {"title": result["title"], "hits": 0})
            entry["hits"] += 1

    # Pages returned for several phrases are the most promising, so check those first.
    urls = sorted(found, key=lambda u: found[u]["hits"], reverse=True)[:MAX_PAGES]

    def load(url: str):
        try:
            return url, fetch(url), None
        except WebCheckError as err:
            return url, None, str(err)
        except (OSError, ValueError, http.client.HTTPException) as err:  # network, decoding, protocol
            return url, None, type(err).__name__

    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = list(pool.map(load, urls))

    report = Document.from_text("document", text, fingerprint, k, w)
    sources, skipped = [], []
    matched: set[int] = set()
    for url, page_text, error in pages:
        if error is not None:
            skipped.append({"url": url, "reason": error})
            continue
        match = compare(report, Document.from_text(url, page_text, fingerprint, k, w))
        if not match.shared:
            continue
        matched |= match.shared
        ranges = [report.char_range(s, e) for s, e in shared_passages(report, match.shared, k)]
        sources.append({
            "url": url,
            "title": found[url]["title"] or urllib.parse.urlsplit(url).hostname,
            "domain": urllib.parse.urlsplit(url).hostname,
            "score": match.a_in_b,  # share of the document found on this page
            "ranges": ranges,
        })
    sources.sort(key=lambda s: s["score"], reverse=True)

    return {
        "k": k,
        "w": w,
        "queries": searched,
        "pages_checked": len(pages) - len(skipped),
        "skipped": skipped,
        "sources": sources,
        "overall": len(matched) / len(report.hashes) if report.hashes else 0.0,
        "ranges": [report.char_range(s, e) for s, e in shared_passages(report, frozenset(matched), k)],
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
