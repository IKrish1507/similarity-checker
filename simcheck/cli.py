"""Command line: python -m simcheck samples/"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

from . import engine
from .compare import Document, compare_all, shared_passages


def collect_files(inputs: list[str]) -> list[Path]:
    """Expand folders (to their .txt files) and wildcards.

    Windows shells do not expand *.txt for us, so we do it here.
    """
    files: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*.txt")))
        elif any(ch in item for ch in "*?["):
            files.extend(Path(p) for p in sorted(glob.glob(item)))
        else:
            files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="simcheck", description="Find shared passages between text documents."
    )
    parser.add_argument("inputs", nargs="+", help=".txt files or folders")
    parser.add_argument("-k", type=int, default=5, help="words per k-gram (default 5)")
    parser.add_argument("-w", type=int, default=4, help="winnowing window (default 4)")
    parser.add_argument("--engine", choices=engine.ENGINES, default="auto")
    parser.add_argument(
        "--threshold", type=float, default=0.10,
        help="show passages for pairs scoring at least this (default 0.10)",
    )
    args = parser.parse_args(argv)

    if args.k < 1 or args.w < 1:
        parser.error("-k and -w must be at least 1")
    files = collect_files(args.inputs)
    if len(files) < 2:
        parser.error(f"need at least 2 documents, found {len(files)}")

    try:
        engine_name, impl = engine.resolve(args.engine)
    except RuntimeError as err:
        parser.error(str(err))

    docs = [
        Document.from_text(
            path.name, path.read_text(encoding="utf-8", errors="replace"),
            impl.fingerprint, args.k, args.w,
        )
        for path in files
    ]

    print(f"Engine: {engine_name}   k={args.k}  w={args.w}   "
          f"(guaranteed to catch copied runs of {args.k + args.w - 1}+ words)\n")
    for doc in docs:
        if not doc.hashes:
            print(f"  note: {doc.name} has fewer than {args.k} words; nothing to compare")

    for m in compare_all(docs):
        print(f"{m.score:6.0%}  {m.a.name} <-> {m.b.name}   "
              f"({m.a.name} in {m.b.name}: {m.a_in_b:.0%}, "
              f"{m.b.name} in {m.a.name}: {m.b_in_a:.0%}, Jaccard {m.jaccard:.0%})")
        if m.score >= args.threshold:
            for start, end in shared_passages(m.a, m.shared, args.k):
                lo, hi = m.a.char_range(start, end)
                text = " ".join(m.a.text[lo:hi].split())  # original wording, one line
                print(f'          "{text[:110]}{"..." if len(text) > 110 else ""}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
