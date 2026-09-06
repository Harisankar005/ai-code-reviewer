"""Unit tests for reviewer.py core functions.
Run with: python test_reviewer.py
"""

import unittest
from reviewer import (
    detect_language_from_filename,
    convert_github_url_to_raw,
    parse_llm_json,
    generate_unified_diff
)


class TestReviewer(unittest.TestCase):

    def test_detect_language(self):
        self.assertEqual(detect_language_from_filename("main.py"), "python")
        self.assertEqual(detect_language_from_filename("app.ts"), "typescript")
        self.assertEqual(detect_language_from_filename("index.js"), "javascript")
        self.assertEqual(detect_language_from_filename("server.go"), "go")
        self.assertEqual(detect_language_from_filename("lib.rs"), "rust")
        self.assertEqual(detect_language_from_filename("unknown.xyz"), "auto")

    def test_convert_github_url_to_raw(self):
        blob_url = "https://github.com/psf/requests/blob/main/requests/api.py"
        expected = "https://raw.githubusercontent.com/psf/requests/main/requests/api.py"
        self.assertEqual(convert_github_url_to_raw(blob_url), expected)

        raw_url = "https://raw.githubusercontent.com/psf/requests/main/requests/api.py"
        self.assertEqual(convert_github_url_to_raw(raw_url), raw_url)

        direct_raw_github = "https://github.com/psf/requests/raw/main/requests/api.py"
        self.assertEqual(convert_github_url_to_raw(direct_raw_github), expected)

    def test_parse_llm_json_strict(self):
        raw = """{
            "findings": [
                {
                    "line": 5,
                    "severity": "high",
                    "issue": "SQL Injection",
                    "explanation": "Query uses raw string formatting."
                }
            ],
            "fixed_code": "cursor.execute('SELECT * FROM users WHERE id = %s', (uid,))",
            "summary": "Fixed SQL injection vulnerability."
        }"""
        result = parse_llm_json(raw)
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["severity"], "high")
        self.assertEqual(result["findings"][0]["line"], 5)
        self.assertIn("SELECT * FROM", result["fixed_code"])
        self.assertEqual(result["summary"], "Fixed SQL injection vulnerability.")

    def test_parse_llm_json_fenced(self):
        raw = """```json
{
    "findings": [],
    "fixed_code": "print('hello world')",
    "summary": "No issues found."
}
```"""
        result = parse_llm_json(raw)
        self.assertEqual(len(result["findings"]), 0)
        self.assertEqual(result["fixed_code"], "print('hello world')")
        self.assertEqual(result["summary"], "No issues found.")

    def test_parse_llm_json_fallback(self):
        raw = "Here is an unstructured response that isn't JSON."
        result = parse_llm_json(raw)
        self.assertIn("findings", result)
        self.assertIn("fixed_code", result)
        self.assertIn("summary", result)

    def test_generate_unified_diff(self):
        original = "def add(a, b):\n    return a - b\n"
        fixed = "def add(a, b):\n    return a + b\n"
        diff = generate_unified_diff(original, fixed, "calc.py")
        self.assertIn("-    return a - b", diff)
        self.assertIn("+    return a + b", diff)


if __name__ == "__main__":
    unittest.main()
