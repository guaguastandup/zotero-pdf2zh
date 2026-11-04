"""Real issue-derived error explanations and conservative non-matches."""

import unittest
from utils.error_catalog import classify_error_message, classify_error_blob


class ErrorCatalogTests(unittest.TestCase):
    def test_bitstring_5_import_regression_issue_366(self):
        result = classify_error_blob(
            'File ".../pdf_creater.py", line 16, in <module>\n'
            '    from bitstring import BitStream\n'
            "ImportError: cannot import name 'BitStream' from 'bitstring'\n"
        )
        self.assertEqual(result["errorCode"], "BITSTRING_INCOMPATIBLE")
        self.assertIn("doctor", result["hint"])

    def test_http_429_and_explicit_key_errors(self):
        self.assertEqual(
            classify_error_message("Error: status code 429 - Too Many Requests")[
                "errorCode"
            ], "API_RATE_LIMIT",
        )
        self.assertEqual(
            classify_error_message("AuthenticationError: invalid_api_key")[
                "errorCode"
            ], "API_AUTH_FAILED",
        )

    def test_unrelated_errors_remain_unknown(self):
        for message in (
            "BabelDOC raised an exception",
            "some text mentions bitstring",
            "There are 429 figures in the PDF",
            "Connection timed out",
        ):
            with self.subTest(message=message):
                self.assertEqual(
                    classify_error_message(message)["errorCode"], "UNKNOWN_ERROR"
                )


if __name__ == "__main__":
    unittest.main()
