"""Source selection is bounded probing; only the visible installer resolves packages."""
import contextlib
import io
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import environment_lifecycle as lifecycle
from utils.package_network import IndexProbeResult


class InstallSourcesTests(unittest.TestCase):
    def test_probing_never_starts_a_package_resolver_and_honors_custom_source(self):
        results = [
            IndexProbeResult("Slow", "https://slow.test/simple", "pdf2zh-next", True, 90, 90),
            IndexProbeResult("Failed", "https://failed.test/simple", "pdf2zh-next", False),
            IndexProbeResult("Fast", "https://fast.test/simple", "pdf2zh-next", True, 10, 10),
            IndexProbeResult("Custom", "https://custom.test/simple", "pdf2zh-next", True, 99, 99),
        ]
        with patch.object(lifecycle, "probe_indexes", return_value=results), \
                patch.object(lifecycle.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            sources = lifecycle.choose_install_sources("pdf2zh_next", "conda", Path("python"), ["pdf2zh-next"])
        run.assert_not_called()
        self.assertEqual(sources, [r.url for r in (results[3], results[2], results[0])])

    def test_real_install_retries_next_source_after_resolution_failure_or_timeout(self):
        for tool in ("uv", "conda"):
            for failure in (subprocess.CalledProcessError(1, "install"), subprocess.TimeoutExpired("install", 1200)):
                with self.subTest(tool=tool, failure=type(failure).__name__), \
                        patch.object(lifecycle.shutil, "which", return_value="/test/uv"), \
                        patch.object(lifecycle.subprocess, "run", side_effect=[failure, None]) as run, \
                        contextlib.redirect_stdout(io.StringIO()):
                    self.assertTrue(lifecycle._run_install(tool, Path("/test/python"), ["pdf2zh-next==2.10.2"], ["https://first.test/simple", "https://next.test/simple"]))
                    self.assertEqual(run.call_count, 2)
                    for call, url in zip(run.call_args_list, ("https://first.test/simple", "https://next.test/simple")):
                        command = call.args[0]
                        self.assertNotIn("--dry-run", command)
                        self.assertEqual(command[command.index("--index-url") + 1], url)
                        self.assertNotIn("capture_output", call.kwargs)
                        self.assertEqual(call.kwargs["timeout"], 1200)

    def test_no_reachable_source_does_not_try_install(self):
        with patch.object(lifecycle, "probe_indexes", return_value=[]), \
                patch.object(lifecycle.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            sources = lifecycle.choose_install_sources("pdf2zh_next", "conda", Path("python"), [])
            self.assertFalse(lifecycle._run_install("conda", Path("python"), [], sources))
        run.assert_not_called()
