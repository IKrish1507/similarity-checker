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
  web.py             local web server (python -m simcheck.web)
  static/index.html  the web page
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

## simcheck/web.py (local web server)

Built on Python's standard `http.server`, so there's nothing to install.

- **`analyze(payload)`** does the real work and is separate from the
  web server, so it can be tested directly. It checks the request
  (2–50 documents, each with a text `name` and `text`, `k` and `w`
  between 1 and 50), fingerprints the documents and returns each pair's
  scores plus **character ranges** to highlight in both documents.
  Anything invalid raises `ValueError`, which becomes an HTTP 400 error.
- **`Handler`** answers three addresses:
  `GET /` (the page), `GET /api/samples` (the sample documents) and
  `POST /api/compare` (runs `analyze`).
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

## simcheck/static/index.html (the page)

Plain HTML, CSS and JavaScript, with no frameworks.

- **Document cards:** each card has a name and a text box. "Load .txt
  files" reads files in the browser with `file.text()`. They are only sent
  to your own local server.
- **`run()`** sends the documents to `/api/compare` with `fetch` and
  shows any error message from the server.
- **`render()`** lists every pair with its score bar. Clicking a pair
  calls **`showPair()`**, which shows both documents side by side.
- **`highlight()`** builds the highlighted text from DOM nodes: plain
  text pieces plus `<mark>` elements whose `textContent` is set. It never
  uses `innerHTML` with document text, so a document containing
  `<script>` is displayed as text instead of running. That bug class is
  called **XSS (cross-site scripting)**, and avoiding it is worth pointing
  out in interviews.
- Colours are CSS variables with a dark-mode set under
  `prefers-color-scheme: dark`.

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
