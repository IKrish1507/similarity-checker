import os
import unittest
from pathlib import Path
from unittest import mock

from simcheck import engine, web, webcheck
from simcheck.aicheck import ai_check
from simcheck.sentences import split_sentences
from simcheck.webcheck import WebCheckError, check_public_url, html_to_text, pick_queries
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


class SentenceTests(unittest.TestCase):
    def test_splits_on_punctuation_and_line_breaks_with_positions(self):
        text = "Heading\nFirst one. Second one!  Third?"
        self.assertEqual([text[s:e] for s, e in split_sentences(text)], ["Heading", "First one.", "Second one!", "Third?"])


class AiCheckTests(unittest.TestCase):
    def sample(self, name):
        return (SAMPLES / "ai-check" / name).read_text(encoding="utf-8")

    def test_ai_style_sample_scores_far_above_human_style_sample(self):
        ai, human = ai_check(self.sample("ai_style.txt")), ai_check(self.sample("human_style.txt"))
        self.assertGreaterEqual(ai["score"], 60)
        self.assertLess(human["score"], 30)

    def test_flags_explain_which_words_triggered(self):
        result = ai_check(self.sample("ai_style.txt"))
        reasons = " ".join(r for f in result["flagged"] for r in f["reasons"])
        self.assertIn('"delve"', reasons)
        self.assertIn("stock transition", reasons)

    def test_short_text_gets_no_score(self):
        result = ai_check("Too short to judge. Really short.")
        self.assertFalse(result["enough_text"])
        self.assertIsNone(result["score"])


PAGE_HTML = """<html><head><title>t</title><script>var hidden = "Hives need regular";</script></head>
<body><nav>Menu</nav><p>Hives need regular inspections to check for pests, disease and signs
that the colony is preparing to swarm.</p></body></html>"""


class WebCheckTests(unittest.TestCase):
    def test_queries_are_quoted_phrases_taken_from_the_text(self):
        text = (SAMPLES / "original.txt").read_text(encoding="utf-8")
        queries = pick_queries(text)
        self.assertTrue(queries)
        for q in queries:
            self.assertTrue(q.startswith('"') and q.endswith('"'))
            self.assertIn(q.strip('"').split()[0], text)

    def test_html_text_skips_scripts_and_navigation(self):
        text = html_to_text(PAGE_HTML)
        self.assertIn("Hives need regular inspections", text)
        self.assertNotIn("var hidden", text)
        self.assertNotIn("Menu", text)

    def test_refuses_local_and_non_web_addresses(self):
        for url in ("http://127.0.0.1/admin", "http://localhost:8000/", "http://10.0.0.1/",
                    "http://169.254.169.254/latest/meta-data", "file:///C:/Windows/win.ini", "ftp://example.com/"):
            with self.assertRaises(WebCheckError, msg=url):
                check_public_url(url)

    def test_finds_the_page_containing_copied_text(self):
        text = (SAMPLES / "copied.txt").read_text(encoding="utf-8")
        pages = {"https://example.com/bees": PAGE_HTML, "https://example.com/bread": "<p>Bread needs flour.</p>"}
        searched = []

        def search(query):
            searched.append(query)
            return [{"url": u, "title": u.rsplit("/", 1)[1]} for u in pages]

        result = webcheck.web_check(text, search=search, fetch=lambda u: html_to_text(pages[u]),
                                    fingerprint=fingerprint, pause=0)
        self.assertEqual([s["url"] for s in result["sources"]], ["https://example.com/bees"])
        self.assertGreater(result["overall"], 0)
        self.assertEqual(result["pages_checked"], 2)
        self.assertEqual(len(result["queries"]), len(searched))
        highlighted = " ".join(text[s:e] for s, e in result["ranges"])
        self.assertIn("Hives need regular inspections", highlighted)

    def test_failed_pages_are_reported_not_fatal(self):
        def fetch(url):
            raise OSError("connection reset")

        result = webcheck.web_check((SAMPLES / "copied.txt").read_text(encoding="utf-8"),
                                    search=lambda q: [{"url": "https://example.com/x", "title": "x"}],
                                    fetch=fetch, fingerprint=fingerprint, pause=0)
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["skipped"], [{"url": "https://example.com/x", "reason": "OSError"}])

    def test_web_check_endpoint_requires_an_api_key(self):
        with mock.patch.dict(os.environ, {web.BRAVE_KEY_VAR: ""}):
            with self.assertRaises(web.NotConfigured):
                web.web_check_request({"text": "anything"})

    def test_ai_check_endpoint_rejects_empty_text(self):
        for payload in ({}, {"text": "   "}, {"text": 5}, []):
            with self.assertRaises(ValueError):
                web.ai_check_request(payload)


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
