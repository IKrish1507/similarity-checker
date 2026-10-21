import unittest
from pathlib import Path

from simcheck import engine, web
from simcheck.compare import Document, compare, shared_passages
from simcheck.fingerprint import fingerprint, fnv1a_64, tokenize, winnow

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def load(name, k=5, w=4):
    return Document.from_text(name, (SAMPLES / name).read_text(encoding="utf-8"), fingerprint, k, w)


class FingerprintTests(unittest.TestCase):
    def test_fnv_matches_published_test_vectors(self):
        self.assertEqual(fnv1a_64(b""), 0xCBF29CE484222325)
        self.assertEqual(fnv1a_64(b"a"), 0xAF63DC4C8601EC8C)

    def test_tokenize_ignores_case_and_punctuation(self):
        self.assertEqual(tokenize("The CAT, sat!  On_the mat."), ["the", "cat", "sat", "on", "the", "mat"])

    def test_winnow_picks_rightmost_minimum_once(self):
        self.assertEqual(winnow([5, 1, 1, 7, 9], 3), [(1, 2)])
        self.assertEqual(winnow([], 4), [])

    def test_shared_run_of_w_plus_k_minus_1_words_is_always_caught(self):
        k, w = 5, 4
        run = " ".join(f"shared{i}" for i in range(k + w - 1))
        a = Document.from_text("a", "x " * 20 + run, fingerprint, k, w)
        b = Document.from_text("b", run + " y" * 20, fingerprint, k, w)
        self.assertTrue(compare(a, b).shared)

    def test_rejects_zero_parameters(self):
        with self.assertRaises(ValueError):
            fingerprint(["a"], 0, 4)


class CompareTests(unittest.TestCase):
    def test_copied_text_scores_higher_than_unrelated(self):
        original, copied, unrelated = load("original.txt"), load("copied.txt"), load("unrelated.txt")
        self.assertGreater(compare(copied, original).a_in_b, 0.3)
        self.assertLess(compare(original, unrelated).score, 0.05)

    def test_passages_recover_the_copied_sentence_in_original_wording(self):
        original, copied = load("original.txt"), load("copied.txt")
        m = compare(copied, original)
        texts = [copied.text[slice(*copied.char_range(s, e))] for s, e in shared_passages(copied, m.shared, 5)]
        self.assertTrue(any("Hives need regular inspections to check for pests, disease" in t for t in texts))

    def test_spans_point_at_the_original_characters(self):
        doc = Document.from_text("d", "Hello,  WORLD!", fingerprint, 1, 1)
        self.assertEqual(doc.tokens, ["hello", "world"])
        self.assertEqual(doc.text[slice(*doc.char_range(0, 2))], "Hello,  WORLD")


class WebApiTests(unittest.TestCase):
    def test_ranges_highlight_the_copied_text_in_both_documents(self):
        docs = [{"name": p.name, "text": p.read_text(encoding="utf-8")} for p in sorted(SAMPLES.glob("*.txt"))]
        result = web.analyze({"documents": docs, "k": 5, "w": 4})
        top = result["pairs"][0]
        self.assertEqual({docs[top["a"]]["name"], docs[top["b"]]["name"]}, {"copied.txt", "original.txt"})
        for side in ("a", "b"):
            text = docs[top[side]]["text"]
            highlighted = " ".join(text[s:e] for s, e in top[f"{side}_ranges"])
            self.assertIn("Hives need regular inspections", highlighted)

    def test_rejects_bad_requests(self):
        one_doc = {"documents": [{"name": "a", "text": "x"}]}
        bad_k = {"documents": [{"name": "a", "text": "x"}, {"name": "b", "text": "y"}], "k": 0}
        bad_doc = {"documents": [{"name": "a"}, {"name": "b", "text": "y"}]}
        for payload in ([], one_doc, bad_k, bad_doc):
            with self.assertRaises(ValueError):
                web.analyze(payload)


@unittest.skipIf(engine.rust_engine is None, "Rust core not built")
class RustParityTests(unittest.TestCase):
    def test_rust_matches_python_on_every_sample(self):
        for path in SAMPLES.glob("*.txt"):
            tokens = tokenize(path.read_text(encoding="utf-8"))
            for k, w in [(1, 1), (3, 2), (5, 4), (8, 10)]:
                self.assertEqual(
                    engine.rust_engine.fingerprint(tokens, k, w), fingerprint(tokens, k, w), (path.name, k, w)
                )


if __name__ == "__main__":
    unittest.main()
