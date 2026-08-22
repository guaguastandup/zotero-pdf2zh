import os
import unittest
from pathlib import Path
from urllib.parse import quote, unquote


ROOT = Path(__file__).resolve().parents[2]
SERVER_SOURCE = (ROOT / "server" / "server.py").read_text(encoding="utf-8")


class DownloadFilenameRoutingTests(unittest.TestCase):
    def test_literal_percent_sequences_survive_one_route_decode(self):
        for original in (
            "paper%2Fname.pdf",
            "paper%20name.pdf",
            "paper%25name.pdf",
        ):
            encoded_path_segment = quote(original, safe="")
            werkzeug_route_value = unquote(encoded_path_segment)
            self.assertEqual(os.path.basename(werkzeug_route_value), original)

    def test_download_handler_does_not_decode_route_parameter_twice(self):
        handler = SERVER_SOURCE.split("def download_file(self, filename):", 1)[1]
        handler = handler.split("#############################", 1)[0]
        self.assertNotIn("unquote(", handler)
        self.assertIn("os.path.basename(filename or '')", handler)


if __name__ == "__main__":
    unittest.main()
