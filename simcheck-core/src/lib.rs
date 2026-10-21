//! Rust core for simcheck: hash k-grams and winnow them into fingerprints.
//!
//! Must produce exactly the same output as simcheck/fingerprint.py.
//! Python owns tokenizing; this crate only receives the list of words.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const FNV_OFFSET: u64 = 0xcbf29ce484222325;
const FNV_PRIME: u64 = 0x100000001b3;

/// Feed more bytes into an FNV-1a 64-bit hash.
fn fnv1a_update(mut hash: u64, bytes: &[u8]) -> u64 {
    for &byte in bytes {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME); // wrapping = the "& MASK64" in Python
    }
    hash
}

/// Hash every run of k consecutive words, joined by single spaces.
///
/// Hashing word, space, word... directly gives the same result as Python's
/// `" ".join(...)` without building a new string for every k-gram.
fn hash_kgrams(tokens: &[String], k: usize) -> Vec<u64> {
    if tokens.len() < k {
        return Vec::new();
    }
    tokens
        .windows(k)
        .map(|gram| {
            let mut hash = FNV_OFFSET;
            for (i, word) in gram.iter().enumerate() {
                if i > 0 {
                    hash = fnv1a_update(hash, b" ");
                }
                hash = fnv1a_update(hash, word.as_bytes());
            }
            hash
        })
        .collect()
}

/// Keep the smallest hash in each window of w (rightmost on ties).
/// Returns (hash, position) pairs.
fn winnow(hashes: &[u64], w: usize) -> Vec<(u64, usize)> {
    if hashes.is_empty() {
        return Vec::new();
    }
    let w = w.min(hashes.len());
    let mut picked = Vec::new();
    let mut last: Option<usize> = None;
    for start in 0..=hashes.len() - w {
        let mut pos = start;
        for j in start..start + w {
            if hashes[j] <= hashes[pos] {
                pos = j;
            }
        }
        if last != Some(pos) {
            picked.push((hashes[pos], pos));
            last = Some(pos);
        }
    }
    picked
}

/// Python-callable: simcheck_core.fingerprint(tokens, k, w)
#[pyfunction]
fn fingerprint(tokens: Vec<String>, k: usize, w: usize) -> PyResult<Vec<(u64, usize)>> {
    if k == 0 || w == 0 {
        return Err(PyValueError::new_err("k and w must be at least 1"));
    }
    Ok(winnow(&hash_kgrams(&tokens, k), w))
}

/// Registers the module so `import simcheck_core` works in Python.
#[pymodule]
fn simcheck_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fingerprint, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fnv_matches_published_test_vectors() {
        assert_eq!(fnv1a_update(FNV_OFFSET, b""), 0xcbf29ce484222325);
        assert_eq!(fnv1a_update(FNV_OFFSET, b"a"), 0xaf63dc4c8601ec8c);
    }

    #[test]
    fn kgram_hash_equals_hash_of_joined_string() {
        let tokens: Vec<String> = ["the", "cat", "sat"].iter().map(|s| s.to_string()).collect();
        assert_eq!(hash_kgrams(&tokens, 3), vec![fnv1a_update(FNV_OFFSET, b"the cat sat")]);
    }

    #[test]
    fn winnow_picks_rightmost_minimum_once() {
        assert_eq!(winnow(&[5, 1, 1, 7, 9], 3), vec![(1, 2)]);
        assert_eq!(winnow(&[], 4), vec![]);
    }
}
