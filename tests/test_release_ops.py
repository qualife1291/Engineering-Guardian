"""Release, documentation, diagnostic and security regression tests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from ucg import __version__
from ucg.diagnostics import Diagnostics, diagnostic_summary, support_bundle
from ucg.engine import SourceChangedDuringScan, scan_workspace
from ucg.scanner import scan_files

PROJECT = Path(__file__).resolve().parents[1]


class ReleaseAndOperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "data"
        self.root = Path(self.tmp.name) / "source"
        self.root.mkdir()
        self.patch = patch.dict(os.environ, {"GUARDIAN_HOME": str(self.home)})
        self.patch.start()
        self.addCleanup(self.patch.stop)
        (self.root / "a.py").write_text("def run():\n    return 1\n")

    def test_release_files_are_present_and_version_consistent(self):
        import tomllib
        project = tomllib.loads((PROJECT / "pyproject.toml").read_text())
        self.assertEqual(project["project"]["version"], __version__)
        self.assertIn(f"## [{__version__}]", (PROJECT / "CHANGELOG.md").read_text())
        for rel in (
            "README.md", "AGENTS.md", "CLAUDE.md", "SECURITY.md", "CONTRIBUTING.md",
            "docs/PROJECT_MAP.md", "docs/CLAUDE_CODE.md", "docs/DIAGNOSTICS.md",
            "docs/USAGE_EXAMPLES_VI.md", "docs/RELEASING.md", "docs/TESTING.md",
        ):
            with self.subTest(file=rel):
                self.assertTrue((PROJECT / rel).is_file())

    def test_explicit_snapshot_cannot_be_reused_for_different_source(self):
        db = self.home / "index.sqlite"
        scan_workspace(str(self.root), str(db), snapshot_id="fixed-id")
        (self.root / "a.py").write_text("def run():\n    return 2\n")
        with self.assertRaises(SourceChangedDuringScan):
            scan_workspace(str(self.root), str(db), snapshot_id="fixed-id")

    def test_secret_named_python_files_excluded(self):
        (self.root / ".env.production.py").write_text("SECRET_KEY='not-an-index'\n")
        (self.root / "client.key").write_text("PRIVATE KEY\n")
        files, skipped = scan_files(self.root)
        self.assertEqual([f.path for f in files], ["a.py"])
        self.assertIn("sensitive_file", [x["reason"] for x in skipped])

    def test_log_summary_aggregates_metrics_without_source(self):
        secret = "VERY_PRIVATE_987654321"
        log = Diagnostics(self.root)
        log.log("scan", success=True, cache_hit=False, files=3,
                parsed_files=3, reused_files=0, diagnostic_count=1, duration_ms=8.0)
        log.log("scan", success=True, cache_hit=True, files=3,
                parsed_files=0, reused_files=3, diagnostic_count=0, duration_ms=1.0)
        log.log("tool_call", success=False, tool_name="guardian_find_symbol",
                failure_type="RuntimeError", duration_ms=2.0)
        log.log("tool_call", success=True, tool_name="guardian_find_symbol",
                absolute_path="/private/path", query=secret, duration_ms=1.0)
        summary = diagnostic_summary(self.root)
        self.assertEqual(summary["successful_scans"], 2)
        self.assertEqual(summary["cache_hits"], 1)
        self.assertEqual(summary["scan_cache_hit_rate"], 0.5)
        self.assertEqual(summary["parsed_files_total"], 3)
        self.assertEqual(summary["reused_files_total"], 3)
        self.assertEqual(summary["parser_warning_count"], 1)
        self.assertEqual(summary["failures"], 1)
        self.assertEqual(summary["timing"]["scan_ms"]["median_ms"], 4.5)
        bundle = support_bundle(self.root)
        with zipfile.ZipFile(bundle) as zf:
            content = "\n".join(zf.read(k).decode("utf-8") for k in zf.namelist())
        self.assertNotIn(secret, content)
        self.assertNotIn(str(self.root), content)
        self.assertNotIn("/private/path", content)

    def test_cli_log_summary_is_machine_readable(self):
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, "-m", "ucg.cli", "--root", str(self.root), "log-summary"],
            cwd=PROJECT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["failures"], 0)
        self.assertIn("timing", parsed)


if __name__ == "__main__":
    unittest.main()
