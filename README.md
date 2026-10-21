# simcheck (prototype)

A document similarity checker that finds passages shared between text files,
using the **winnowing** fingerprint algorithm (Schleimer, Wilkerson & Aiken,
2003), the same idea behind Stanford's MOSS. Python handles the program;
an optional Rust core does the fingerprinting.

## Run it

```bash
python -m simcheck samples
```

```text
Engine: python   k=5  w=4   (guaranteed to catch copied runs of 8+ words)

   37%  copied.txt <-> original.txt   (copied.txt in original.txt: 37%, ...)
          "beekeeping has grown quickly over the last decade, as more people look for ways to support"
          "honey tastes different from season to season because the flowers in bloom change throughout the"
          "Hives need regular inspections to check for pests, disease and signs that the colony is"
    0%  copied.txt <-> unrelated.txt ...
```

Options: `-k` (words per k-gram), `-w` (window size), `--engine auto|rust|python`,
`--threshold` (minimum score before passages are shown).

## Web page (localhost)

```bash
python -m simcheck.web
```

Open http://127.0.0.1:8000. It works like a chat app:

- Paste text or attach/drag in `.txt` files, then press **Ctrl+Enter**
  (or click **Try the samples**).
- Each check is saved in the sidebar, with search, delete, and
  light/dark themes. Add more documents to a check at any time, and
  they're compared with everything already in it.
- Results show a plain-English summary, a similarity grid, a score ring
  for each pair, and a side-by-side view with highlighted passages. You
  can copy a summary or download the results as JSON.

The server only listens on this computer and uses nothing outside Python's
standard library. History is stored only in your browser.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Enable the Rust core

Needs Rust (https://rustup.rs) and, on Windows, Microsoft C++ Build Tools.

`maturin develop` installs into a virtual environment, so create one first
(on macOS/Linux, use `.venv/bin/` instead of `.venv\Scripts\`):

```bash
python -m venv .venv
.venv\Scripts\python -m pip install maturin
.venv\Scripts\maturin develop --release -m simcheck-core/Cargo.toml
cargo test --manifest-path simcheck-core/Cargo.toml
```

Then run everything with `.venv\Scripts\python` (for example
`.venv\Scripts\python -m simcheck samples`). It reports `Engine: rust`, and
the parity test checks that Rust and Python give identical fingerprints.

See [WALKTHROUGH.md](WALKTHROUGH.md) for an explanation of every file.
