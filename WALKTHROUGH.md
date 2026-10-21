# Code walkthrough

## The big idea

Comparing every sentence of every document against every other is far too
slow. Instead, each document is reduced to a small set of **fingerprints**
(numbers). Two documents that share a passage will share some fingerprints,
so comparing documents becomes comparing sets of numbers, which is fast.

```
text ──tokenize──▶ words ──k-grams──▶ hashes ──winnow──▶ fingerprints ──compare──▶ scores + passages
        (Python)              (Rust or Python)                              (Python)
```

## Project layout

```
simcheck/            Python package (the program)
  fingerprint.py     tokenize, hashing, winnowing (pure-Python reference)
  engine.py          picks the Rust core or the Python fallback
  compare.py         similarity scores and shared passages
  cli.py             command line interface
  sentences.py       sentence splitting shared by the checks below
  aicheck.py         AI-writing pattern estimate
  webcheck.py        web source check (search, safe download, compare)
  web.py             local web server (python -m simcheck.web)
  static/            the web app: index.html, app.css, app.js
  __main__.py        lets you run `python -m simcheck`
simcheck-core/       Rust crate, compiled into a Python module
  src/lib.rs         the same fingerprint algorithm, in Rust
  Cargo.toml         Rust build settings
  pyproject.toml     tells maturin how to package it for Python
samples/             three test documents (original, partly copied, unrelated)
tests/               unit tests
```

---

## simcheck/fingerprint.py

### `tokenize_with_spans(text)` and `tokenize(text)`
Pulls out runs of letters and digits with the regex `[^\W_]+` and
lowercases each one. `\W` means "not a word character", so `[^\W_]` means
"a word character that isn't `_`". Punctuation and spacing disappear, which
means `"Cities!"` and `"cities"` are treated as the same word. That makes
simple disguises like changing punctuation useless.

It also records each word's **span**: its start and end character position
in the original text. Later, a match covering words 12–30 can be turned
back into the exact original sentence, with its capitals and punctuation.
Each word is lowercased *after* finding it, because lowercasing the whole
text first can change its length for a few unusual characters (Turkish `İ`
becomes two characters), which would shift every position after it.

`tokenize` is the same function, keeping only the words.

### `fnv1a_64(data)`
A hash function turns any text into a 64-bit number. We use **FNV-1a**
because it is tiny and gives the same number everywhere. For each byte:
XOR it into the hash, then multiply by a fixed prime. `& MASK64` keeps the
result within 64 bits, because Python integers would otherwise keep growing.

Why not Python's built-in `hash()`? It is randomised each time Python
starts (a security feature), so Rust and Python, or two runs, would disagree.

### `hash_kgrams(tokens, k)`
A **k-gram** is k words in a row. With k=5, the words
`a b c d e f` give `a b c d e`, `b c d e f`. Each k-gram is joined with
spaces and hashed. One hash per starting word.

k is the trade-off: small k gives false matches on common phrases like
"in the middle of the", while large k misses copying with small edits.

### `winnow(hashes, w)`
Keeping every hash works but is big. Winnowing keeps a few: slide a
window of w hashes along the list and keep the **smallest** in each window.
Neighbouring windows usually share the same minimum, so it is only recorded
once (`pos != last`). Choosing the *rightmost* minimum on ties is part of
the published algorithm. It keeps the choice consistent between documents.

**The guarantee:** if two documents share a run of at least `w + k - 1`
words, at least one window falls entirely inside that run in both, and both
pick the same minimum, so they share a fingerprint. With k=5, w=4: any
copied run of 8+ words is always caught.

Each fingerprint is `(hash, position)`. The position (index of the first
word) lets us show *where* the match is later.

### `fingerprint(tokens, k, w)`
Validates `k` and `w`, then runs `hash_kgrams` and `winnow`. The Rust core
exposes a function with this exact name and arguments, which is what lets
the two be swapped.

---

## simcheck/engine.py

Tries `import simcheck_core` (the compiled Rust module). If that fails,
`rust_engine` is `None`. `resolve()` returns whichever engine to use:

- `auto`: Rust if installed, otherwise Python
- `python`: always Python
- `rust`: Rust, or an error if it is missing. Never a silent fallback, so
  the output's `Engine:` line is always true.

---

## simcheck/compare.py

### `Document`
Holds a document's name, original text, words, word spans, the set of
fingerprint hashes (for fast set maths), and `positions`, which maps each
hash to where it appears. `Document.from_text` builds all of that once,
using whichever engine's `fingerprint` function it is given (Rust or
Python). `char_range(start, end)` converts a range of words into a range of
characters in the original text.

### `Match` and `compare(a, b)`
`shared = a.hashes & b.hashes` is the set intersection. Three scores:

| Score | Meaning |
|---|---|
| `a_in_b` | share of A's fingerprints found in B ("how much of A appears in B") |
| `b_in_a` | the same, the other way round |
| `jaccard` | shared / everything in either document (overall overlap) |

Containment (`a_in_b`) matters most for plagiarism. A short essay copied
entirely from a long article is 100% contained but has a low Jaccard.
`score` is the larger of the two containments.

### `compare_all(docs)`
`itertools.combinations` produces every pair once (A–B, not also B–A),
then the pairs are sorted by score, highest first.

### `shared_passages(doc, shared, k)`
Each shared fingerprint covers words `[pos, pos + k)`. The ranges are
sorted, and any range that overlaps or touches the previous one is merged
into it, so many small hits become one readable passage.

---

## simcheck/cli.py

- `collect_files` turns folders into their `.txt` files and expands
  wildcards (`samples/*.txt`) itself, because Windows shells don't.
- `main` reads the arguments, checks them (`k`, `w` ≥ 1, at least two
  files), picks the engine, fingerprints each file, then prints every pair
  and, above the threshold, its shared passages.
- Files are read as UTF-8 with `errors="replace"`, so one odd character
  can't crash the program.
- Passages are printed in their original wording via `char_range`, with
  line breaks collapsed so each passage fits on one line.

---

## simcheck/sentences.py

`split_sentences(text)` returns the character range of every sentence: a
run of text up to `.`, `!`, `?` or a line break, plus any closing quote or
bracket. Positions are kept so sentences can be highlighted later.
It's deliberately simple, so "e.g." and "Dr." end a sentence early, which is
fine for the estimates it's used for. `words(text)` counts words for
statistics, keeping "don't" and "well-known" whole.

---

## simcheck/aicheck.py (AI-writing check)

**What it is:** a transparent heuristic, not a trained AI model. It measures
five patterns that AI assistants produce more often than most people do:

| Signal | Weight | What's measured | Scored 0 → 1 between |
|---|---|---|---|
| Even sentence lengths | 35% | standard deviation ÷ mean of sentence lengths ("coefficient of variation") | 0.65 → 0.30 |
| AI-typical wording | 30% | hits from the `AI_PHRASES` list per 1,000 words | 0 → 8 |
| Stock transitions | 15% | share of sentences starting "Furthermore", "Moreover"… | 5% → 25% |
| Three-part lists | 10% | share of sentences with an "X, Y, and Z" list | 5% → 30% |
| Em-dash use | 10% | em dashes per 1,000 words | 0 → 6 |

- **`_scale(value, low, high)`** maps a measurement onto 0–1 in a straight
  line, clamped at both ends. Each signal's score is multiplied by its
  weight and the results are added up into a score out of 100.
- **Bands:** under 30 "Few", 30–59 "Some", 60+ "Many" AI-style patterns.
- **Flagged sentences** list the reasons they were flagged (which words,
  which opener), so the result can be checked by a person.
- **Guards:** below 150 words or 5 real sentences it returns no score,
  because statistics on tiny samples are meaningless.
- **Regexes:** the phrase list is compiled into one regex, longest
  phrases first, so "it is important to note" wins over shorter overlaps.
  `(?<![\w-])` and `(?![\w-])` act like word boundaries that also respect
  hyphens.

**Limits (shown in the UI as well):** this cannot prove anything. Formal
academic writing and non-native English writers often score high, edited
AI text can score low, and the thresholds were chosen by hand, not
measured on a labelled dataset. Commercial detectors have the same
fundamental problem. On the two samples in `samples/ai-check/` (both written
for this project) the AI-style text scores 90 and the casual human text
scores 5. That shows the signals behave as designed; it is **not** an
accuracy measurement.

---

## simcheck/webcheck.py (web source check)

How real plagiarism checkers search the web, in four steps:

1. **`pick_queries`**: take the first 14 words of each long sentence (10+
   words), score each candidate by how many long, uncommon words it has,
   split the document into 8 equal parts and pick the best candidate from
   each. Quoted phrases make the search engine look for that exact wording.
2. **`brave_search(api_key)`** returns a search function that calls the
   Brave Search API. Errors become `WebCheckError` with plain messages: a
   wrong key, an exhausted free credit (HTTP 429) or no connection. The key
   is sent only in the request header and never appears in messages.
   Searches are spaced 1.1 s apart because Brave's free plan allows about
   one request per second.
3. **`fetch_page_text`** downloads each page (up to 12, those returned for
   the most phrases first, 6 at a time in parallel) with a 10 s timeout
   and a 2 MB cap, accepts only HTML or plain text, and extracts the
   readable text with `_TextExtractor`, which skips scripts, styles,
   navigation and footers.
4. **`web_check`** fingerprints every page and compares it with the
   document. Each source gets "how much of your document is on this page"
   plus highlight ranges, and the overall figure is the share of the
   document's fingerprints found on *any* page. Pages that fail to download
   are listed with the reason instead of failing the whole check.

**SSRF protection (`check_public_url`).** The server downloads URLs that
come from search results, which we don't control. A malicious result could
point at `http://192.168.1.1/` (your router) or a cloud metadata address
(`169.254.169.254`), making your computer fetch something private. That is
called **server-side request forgery (SSRF)**. So every URL, and every
redirect hop (`_CheckedRedirects`), must be http(s) and resolve only to
public IP addresses (`ipaddress.ip_address(...).is_global`). Remaining
gap: the address is checked, then connected to separately, so a hostile DNS
server could change the answer in between ("DNS rebinding"). Closing that
needs connecting to the exact checked IP, which is planned for the final
version.

**Testing without a key:** `web_check` takes `search` and `fetch` as
parameters ("dependency injection"), so the tests pass fake functions and
check the whole pipeline without touching the internet.

---

## simcheck/web.py (local web server)

Built on Python's standard `http.server`, so there's nothing to install.

- **`analyze(payload)`** does the real work and is separate from the
  web server, so it can be tested directly. It checks the request
  (2–50 documents, each with a text `name` and `text`, `k` and `w`
  between 1 and 50), fingerprints the documents and returns each pair's
  scores plus **character ranges** to highlight in both documents.
  Anything invalid raises `ValueError`, which becomes an HTTP 400 error.
- **`Handler`** answers these addresses:
  - `GET /`, `/static/app.css`, `/static/app.js`: the page files. Only the
    files listed in `STATIC_FILES` are served, so a request like
    `/static/../../secret.txt` can't read other files on disk ("path
    traversal").
  - `GET /api/info`: which engine is active, the limits, and whether
    web search is set up.
  - `GET /api/samples` (`?set=ai` for the AI-check samples).
  - `POST /api/compare`: runs `analyze`, which also reports how long the
    comparison took (`elapsed_ms`).
  - `POST /api/ai-check` and `POST /api/web-check`: take `{"text": ...}`.
  POST routes are looked up in the `POST_ROUTES` table. Errors map to
  HTTP codes: bad input → 400, web check without a key → 503
  (`NotConfigured`), search or download failure → 502 (`WebCheckError`).
- **The Brave key** is read from the `BRAVE_SEARCH_API_KEY` environment
  variable, so it is never stored in code, in the browser or on GitHub.
- **Safety limits:**
  - It listens on `127.0.0.1` only, so other computers on your Wi-Fi can't
    reach it.
  - Requests over 5 MB are refused before being read, so a huge upload
    can't use up memory.
  - The `Host` header must be `127.0.0.1` or `localhost`. This blocks
    *DNS rebinding*, a trick where a malicious website points its own
    domain name at your computer so your browser talks to your local server.
- `ThreadingHTTPServer` handles each request on its own thread, so one
  slow comparison doesn't freeze the page.

## The web app (simcheck/static/)

A chat-style interface in plain HTML, CSS and JavaScript, with no frameworks
and no build step. Each **check** works like a chat conversation: your
message lists the documents you added, and the reply shows the results. You
can keep adding documents to a check, and each new one is compared with
everything already there.

### index.html: the structure
- **Sidebar:** "New check", search box, history list, a settings panel
  (k and w sliders) and the theme switch (system / light / dark).
- **Main area:** a top bar (title, engine badge, help button), the thread,
  and the composer.
- A tiny script in `<head>` applies the saved theme *before* the page
  draws, so a dark-mode user never sees a white flash.
- `<span data-icon="...">` placeholders are swapped for SVG icons on start-up.

### app.css: the look
- **Design tokens:** every colour is a CSS variable on `:root`. Dark mode
  redefines them in two places: for "system" (`prefers-color-scheme`)
  and when the user picks dark (`[data-theme="dark"]`). Components only
  use the variables, so one change re-themes everything.
- **Layout:** the sidebar and main area are a flex row filling the screen
  (`100dvh`). Collapsing the sidebar slides it out with a negative margin.
  Under 800px wide it becomes an overlay drawer with a dimmed backdrop.
- **Score ring:** a `conic-gradient` circle filled to the score, with a
  smaller circle on top to make a ring. No images or chart library needed.
- **Similarity grid cells** mix the accent colour into the background
  in proportion to the score, using `color-mix()`.
- `[hidden] { display: none !important; }` makes sure the `hidden`
  attribute always wins over class rules like `display: flex`.
- Animations are switched off for users who ask their system for
  reduced motion.

### app.js: the behaviour
Organised top to bottom:

1. **Helpers.** `h(tag, props, ...children)` builds elements. Strings
   always become *text nodes*, never HTML, so a document containing
   `<script>` is shown as text instead of running. That bug class is called
   **XSS (cross-site scripting)**, and avoiding it is worth mentioning in
   interviews. Icons are the only `innerHTML`, and they come from fixed
   strings in the file.
2. **Storage.** History, settings, theme and sidebar state are saved in
   the browser's `localStorage`. Every read and write is wrapped in
   `try/catch`, because storage can be blocked (private windows) or full.
   Loaded data is checked before use, and history keeps the newest 40 checks.
3. **State.** One `state` object holds the checks, the open check,
   documents waiting in the composer, settings and theme. Everything on
   screen is drawn from it.
4. **Sidebar.** `renderHistory()` filters by the search box and groups
   checks into Today / Yesterday / Previous 7 days / Older.
5. **Thread.** `render()` redraws the open check. With no check open, it
   shows the welcome screen with the composer in the middle and three
   suggestion cards. `renderTurn()` draws one request/result pair.
   `renderResult()` writes a plain-English summary, then the similarity
   grid (3+ documents), a card per overlapping pair, and the pairs with no
   overlap folded away.
6. **Pair cards.** Each card shows a score ring, a High / Medium / Low
   badge (≥40% / ≥15% / above 0) and the scores. "Compare side by side"
   builds the viewer: both texts with `<mark>` highlights, plus
   previous/next buttons that scroll each column to its next passage
   (`focusMark`).
7. **Copy and download.** "Copy summary" puts a short text report on the
   clipboard. "Download JSON" saves the scores and passages as a file,
   created in the browser with a `Blob`.
8. **Composer.** Pasted text becomes a document named after its first
   words. `.txt` files come from the paperclip button or drag-and-drop
   (files over 2 MB are refused). Documents appear as chips you can remove
   or rename (double-click).
9. **Modes.** The pill next to the paperclip switches between Compare,
   AI check and Web check (`MODES`, `setMode`, `toggleModeMenu`). AI and
   web checks take exactly one document. Web check shows "needs setup" and
   opens the setup steps until the server reports a key.
10. **Running a check.** `send()` adds the new documents to the open check
   (or starts a new one) and records a *turn* with its `kind`. `runTurn()`
   posts to the matching endpoint. Errors show in the thread with a
   "Try again" button, and a dropped connection gets a hint to restart the
   server. Checks saved before modes existed have no `kind` and are
   treated as comparisons.
11. **AI result** (`renderAiResult`): score ring and band, the "not proof"
    notice *before* any detail, a row per signal with a meter and
    explanation, and the text with flagged sentences highlighted. Hovering
    a highlight shows why it was flagged.
12. **Web result** (`renderWebResult`, `sourceCard`): summary, one card per
    matching page with a link and "Show matches", plus folded sections for
    all matches, the exact phrases searched, and pages that couldn't be
    read. Links pass through `safeLink`, so only `http(s)` URLs become
    links. A `javascript:` URL in a search result can't run code, and
    `rel="noopener noreferrer"` stops the opened page from controlling
    this one.
13. **Events.** Ctrl+Enter compares, Ctrl+Shift+O starts a new check,
    Escape closes panels, and drag-and-drop works anywhere on the page.

---

## simcheck-core/src/lib.rs (Rust)

The same algorithm, line for line, so the results are identical:

- `fnv1a_update`: same FNV-1a loop. `wrapping_mul` lets the
  multiplication overflow and wrap around, which is exactly what Python's
  `& MASK64` does.
- `hash_kgrams`: `tokens.windows(k)` gives each run of k words. Instead
  of joining them into a new string (an allocation per k-gram), it feeds
  word, space, word... straight into the hash. Same result, less work.
- `winnow`: the same loop; `Option<usize>` stands in for Python's `-1`.
- `#[pyfunction] fingerprint`: makes the function callable from Python.
  PyO3 converts Python `list[str]` to `Vec<String>` and the returned
  `Vec<(u64, usize)>` back to `list[tuple[int, int]]` automatically.
- `#[pymodule] simcheck_core`: registers the module so
  `import simcheck_core` works.
- `#[cfg(test)] mod tests`: Rust unit tests, run with `cargo test`.

### Cargo.toml / pyproject.toml
- `crate-type = ["cdylib", "rlib"]`: `cdylib` builds the `.pyd` file
  Python loads; `rlib` lets `cargo test` build.
- `abi3-py39`: builds against Python's *stable ABI*, so one compiled file
  works on Python 3.9 up to 3.15.
- `maturin` is the tool that compiles the crate and installs it into
  Python. `extension-module` is only switched on through maturin, because
  turning it on for `cargo test` breaks linking.

---

## tests/test_simcheck.py

- **FNV test vectors:** checks our hash against published values, so a
  typo in a constant can't go unnoticed.
- **Tokenize:** case, punctuation and `_` handling.
- **Winnow:** the rightmost-minimum rule, and empty input.
- **The guarantee:** builds two documents sharing exactly `w + k - 1`
  words and checks they share a fingerprint.
- **Samples:** `copied.txt` must score high against `original.txt`, the
  unrelated document must score near zero, and the copied sentence about
  hive inspections must be found.
- **Rust parity:** when the Rust core is built, its fingerprints must be
  *identical* to Python's for every sample and several k/w settings.

---

## Known prototype limitations (for the final version)

1. **Passages lose their edges.** Winnowing only keeps some k-grams, so a
   reported passage can start or end a few words inside the real copied
   text (e.g. "beekeeping has grown…" misses "Urban"). Fix: extend matches
   word by word in both documents.
2. ~~Passages show normalised words.~~ Fixed: word spans now map matches
   back to the original text.
3. **Only `.txt`.** Add `.docx` and `.pdf` text extraction.
4. ~~Plain-text output only.~~ The local web page now shows side-by-side
   highlighting. A saved, shareable HTML report is still to do.
5. **Every pair is compared** (n² pairs). Fix: an index from hash to
   documents, so only documents that share a fingerprint get compared.
   That is also where Rust (with parallel threads) would pay off most.
6. **Exact wording only.** Paraphrasing and synonyms are not detected,
   which is true of fingerprinting in general.
