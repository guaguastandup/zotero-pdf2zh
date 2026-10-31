"""Regression tests for the bitstring 5.x/BabelDOC compatibility incident."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import manage_packages
from utils import environment_lifecycle as lifecycle


class BitstringHealthTests(unittest.TestCase):
    def _probe_code(self) -> str:
        fake_result = subprocess.CompletedProcess(
            [], 0, stdout='{"ok":true,"reason":"ok"}', stderr=""
        )
        with patch.object(lifecycle.subprocess, "run", return_value=fake_result) as run:
            self.assertEqual(
                lifecycle.managed_runtime_health("pdf2zh_next", Path(sys.executable)),
                (True, "ok"),
            )
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-I", "-c"])
        return command[-1]

    @staticmethod
    def _run_probe(code: str, *, has_bitstream: bool) -> dict:
        modules = {}
        for name in (
            "pydantic",
            "pydantic_core",
            "pydantic_core._pydantic_core",
            "bitstring",
        ):
            module = types.ModuleType(name)
            module.__file__ = str(
                Path(sys.prefix) / "share" / (name.replace(".", "_") + ".py")
            )
            modules[name] = module
        if has_bitstream:
            class BitStream:
                pass

            modules["bitstring"].BitStream = BitStream

        output = io.StringIO()
        with patch.dict(sys.modules, modules):
            with contextlib.redirect_stdout(output):
                exec(code, {})
        return json.loads(output.getvalue())

    def test_missing_bitstream_is_rejected_even_when_package_exists(self):
        result = self._run_probe(self._probe_code(), has_bitstream=False)
        self.assertFalse(result["ok"])
        self.assertIn("BitStream", result["reason"])

    def test_compatible_bitstream_import_and_construction_pass(self):
        result = self._run_probe(self._probe_code(), has_bitstream=True)
        self.assertEqual(result["reason"], "ok")
        self.assertTrue(result["ok"])

    def test_old_custom_config_gets_compatibility_constraint(self):
        config = {
            "pdf2zh_next": {
                "uv": {
                    "python_version": "3.12",
                    "packages": ["pdf2zh_next==2.9.0"],
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "venv.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            _, requirements = lifecycle.load_requirements(
                "pdf2zh_next", "uv", config_path=path
            )
        self.assertIn("bitstring>=4.3.0,<5", requirements)
        self.assertIn("bitstring", lifecycle.VERSION_PACKAGES["pdf2zh_next"])

    def test_conflicting_explicit_pin_is_not_silently_dropped(self):
        config = {
            "pdf2zh_next": {
                "conda": {
                    "python_version": "3.12",
                    "packages": ["pdf2zh_next==2.9.0", "bitstring==5.0.0"],
                }
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "venv.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            _, requirements = lifecycle.load_requirements(
                "pdf2zh_next", "conda", config_path=path
            )
        self.assertIn("bitstring==5.0.0", requirements)
        self.assertIn("bitstring>=4.3.0,<5", requirements)


class DoctorTests(unittest.TestCase):
    def _diagnose(self, bitstring_version: str, health: tuple[bool, str]):
        existing = ("uv", Path("/tmp/managed-next"), Path(sys.executable))
        output = io.StringIO()
        with (
            patch.object(manage_packages, "find_existing_environment", return_value=existing),
            patch.object(
                manage_packages,
                "read_versions",
                return_value={"pdf2zh-next": "2.9.0", "bitstring": bitstring_version},
            ),
            patch.object(manage_packages, "managed_runtime_health", return_value=health),
            patch.object(manage_packages, "server_version_from_source", return_value="4.1.8"),
            patch.object(
                manage_packages,
                "transactional_install_or_update",
                side_effect=AssertionError("doctor must never install"),
            ),
            contextlib.redirect_stdout(output),
        ):
            result = manage_packages.doctor("pdf2zh_next", "auto")
        return result, output.getvalue()

    def test_doctor_exposes_correct_python_and_healthy_import(self):
        ok, output = self._diagnose("4.4.0", (True, "ok"))
        self.assertTrue(ok)
        self.assertIn("Server: 4.1.8", output)
        self.assertIn(str(Path(sys.executable)), output)
        self.assertIn("bitstring 4.4.0", output)
        self.assertIn("bitstring.BitStream", output)

    def test_doctor_rejects_bitstring_5_even_if_health_is_misreported(self):
        ok, output = self._diagnose("5.0.0", (True, "ok"))
        self.assertFalse(ok)
        self.assertIn("不满足", output)
        self.assertIn("python update_packages.py", output)

    def test_doctor_reports_import_failure_with_compatible_metadata(self):
        ok, output = self._diagnose("4.4.0", (False, "ImportError: BitStream missing"))
        self.assertFalse(ok)
        self.assertIn("BitStream missing", output)


if __name__ == "__main__":
    unittest.main()
