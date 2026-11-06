"""Cross-platform docs and menu regression tests (run on Linux and Windows)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from scripts.guardian_menu import parse_user_path

PROJECT = Path(__file__).resolve().parents[1]


class CrossPlatformTests(unittest.TestCase):
    def test_quoted_folder_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="Guardian My Project ") as folder:
            expected = Path(folder).resolve()
            self.assertEqual(parse_user_path('"' + folder + '"'), expected)
            self.assertEqual(parse_user_path("'" + folder + "'"), expected)
            self.assertEqual(parse_user_path(folder), expected)

    def test_posix_escaped_spaces_and_windows_literal_backslashes(self):
        with tempfile.TemporaryDirectory(prefix="Guardian My Project ") as folder:
            if os.name == "nt":
                self.assertEqual(parse_user_path(folder), Path(folder).resolve())
            else:
                self.assertEqual(parse_user_path(folder.replace(" ", r"\ ")), Path(folder).resolve())

    def test_required_portable_entrypoints_and_docs(self):
        required = (
            "Start Engineering Guardian.command",
            "Start Engineering Guardian.cmd",
            "scripts/connect_claude.sh",
            "scripts/connect_claude.ps1",
            "scripts/windows_common.ps1",
            "scripts/start_windows.ps1",
            "docs/WINDOWS_SETUP_VI.md",
            "docs/DOCS_INDEX.md",
            "docs/DEVELOPER_GUIDE.md",
        )
        for item in required:
            with self.subTest(path=item):
                self.assertTrue((PROJECT / item).is_file(), item)

    def test_windows_launcher_does_not_modify_machine_policy(self):
        launcher = (PROJECT / "Start Engineering Guardian.cmd").read_text(encoding="utf-8")
        connector = (PROJECT / "scripts/connect_claude.ps1").read_text(encoding="utf-8")
        self.assertIn("-NoProfile -ExecutionPolicy Bypass -File", launcher)
        self.assertNotIn("Set-ExecutionPolicy", connector)
        self.assertIn("--scope','local'", connector)
        self.assertIn("'--root',$project", connector)

    def test_version_and_docs_entrypoints(self):
        from ucg import __version__
        self.assertEqual(__version__, "0.5.0")
        readme = (PROJECT / "README.md").read_text(encoding="utf-8")
        changelog = (PROJECT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("WINDOWS_SETUP_VI.md", readme)
        self.assertIn("## [0.5.0]", changelog)
        self.assertIn("CALLS", readme)


if __name__ == "__main__":
    unittest.main()
