"""Choose who computes fingerprints: the Rust core or the Python fallback."""

from __future__ import annotations

from . import fingerprint as python_engine

try:
    import simcheck_core as rust_engine  # built from simcheck-core/ with maturin
except ImportError:
    rust_engine = None

ENGINES = ("auto", "rust", "python")


def resolve(choice: str = "auto"):
    """Return (name, module) for the requested engine.

    "auto" prefers Rust when it is installed. Asking for "rust" explicitly
    when it is missing is an error rather than a silent fallback, so you
    always know which code produced a result.
    """
    if choice == "python" or (choice == "auto" and rust_engine is None):
        return "python", python_engine
    if rust_engine is None:
        raise RuntimeError(
            "The Rust engine is not installed. Build it with: "
            "pip install maturin && maturin develop -m simcheck-core/Cargo.toml"
        )
    return "rust", rust_engine
