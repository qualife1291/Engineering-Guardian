"""CI regression checks for generic public examples and AI-free codebase inspection."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ucg.service import GuardianService
from ucg.mcp import GuardianMCP

REPO=Path(__file__).resolve().parents[1]


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"sample project"
        (self.root/"src").mkdir(parents=True)
        (self.root/"lib").mkdir()
        self.cache=Path(self.tmp.name)/"cache"
        env=patch.dict(os.environ,{"GUARDIAN_HOME":str(self.cache)})
        env.start()
        self.addCleanup(env.stop)
        body="def parseConfig():\n    total=0\n"+("    total+=1\n"*110)+"    return total\n"
        (self.root/"src"/"config.py").write_text(body,encoding="utf-8")
        (self.root/"src"/"helper.py").write_text("def helper():\n    return parseConfig()\n",encoding="utf-8")
        (self.root/"lib"/"order.ts").write_text("export function processOrder() { return 1; }\n",encoding="utf-8")
        self.service=GuardianService(str(self.root),diagnostics=False)
        self.service.scan()

    def test_tree_outline_and_hotspots(self):
        tree=self.service.tree(depth=3,limit=30)
        self.assertEqual(tree["indexed_files"],3)
        self.assertIn("src/config.py",{e["path"] for e in tree["entries"]})
        outline=self.service.outline("src/config.py")
        self.assertEqual(outline["lines"],113)
        self.assertEqual(outline["symbols"][0]["name"],"parseConfig")
        self.assertNotIn("total+=1",json.dumps(outline))
        hot=self.service.hotspots(min_lines=50,min_function_lines=40)
        self.assertEqual(hot["flagged_files"],1)
        self.assertIn("long_function",hot["items"][0]["signals"])

    def test_reject_unsafe_outline_paths(self):
        for path in ("../outside.py","/tmp/outside.py","C:\\Users\\example\\x.py","src//config.py"):
            with self.subTest(path="unsafe"),self.assertRaises(ValueError):
                self.service.outline(path)

    def test_offline_map_context_budget_and_freshness(self):
        mapping=self.service.repo_map("processOrder",max_chars=3000,limit=20)
        self.assertIn("processOrder",mapping["text"])
        self.assertIn("parseConfig",mapping["text"])
        self.assertLessEqual(len(mapping["text"]),3000)
        tight=self.service.repo_map("processOrder",max_chars=256)
        self.assertLessEqual(len(tight["text"]),256)
        with self.assertRaises(ValueError):
            self.service.repo_map(max_chars=10)
        (self.root/"src"/"config.py").write_text("def changed():\n    return 2\n",encoding="utf-8")
        with self.assertRaises(Exception):
            self.service.repo_map()

    def test_offline_diff_without_git(self):
        self.assertEqual(self.service.diff()["status"],"no_baseline")
        (self.root/"src"/"helper.py").write_text("def helper():\n    return 0\n",encoding="utf-8")
        (self.root/"src"/"new.py").write_text("def another():\n    return 1\n",encoding="utf-8")
        self.service.scan()
        result=self.service.diff()
        self.assertEqual(result["counts"]["modified_files"],1)
        self.assertEqual(result["counts"]["added_files"],1)
        self.assertEqual(result["counts"]["added_symbols"],1)
        self.assertIn("src/helper.py",result["modified_files"])
        self.assertIn("src/new.py",result["added_files"])

    def test_offline_brief_and_mcp_tools(self):
        brief=self.service.brief("config")
        self.assertIn("Offline Codebase Brief",brief["markdown"])
        self.assertFalse((self.root/"README.md").exists())
        mcp=GuardianMCP(self.service)
        names={r["name"] for r in mcp.dispatch({"jsonrpc":"2.0","id":1,"method":"tools/list"})["result"]["tools"]}
        for n in ("guardian_tree","guardian_outline","guardian_hotspots","guardian_repo_map","guardian_snapshot_diff","guardian_offline_brief"):
            self.assertIn(n,names)
        req={"jsonrpc":"2.0","id":2,"method":"tools/call",
             "params":{"name":"guardian_outline","arguments":{"file":"src/config.py"}}}
        self.assertFalse(mcp.dispatch(req)["result"]["isError"])
        req["params"]["arguments"]["file"]="../private.txt"
        self.assertTrue(mcp.dispatch(req)["result"]["isError"])

    def test_multiple_local_clients_share_snapshot(self):
        from concurrent.futures import ThreadPoolExecutor
        from ucg.diagnostics import diagnostic_summary, support_bundle
        from zipfile import ZipFile
        def lookup(_):
            client=GuardianService(str(self.root))
            return client.repo_map(focus="config",max_chars=2000)["snapshot_id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            snapshot_ids=list(pool.map(lookup,range(8)))
        self.assertEqual(len(set(snapshot_ids)),1)
        metrics=diagnostic_summary(self.root)
        self.assertGreaterEqual(metrics["timing"]["tool_ms"]["count"],8)
        bundle=support_bundle(self.root)
        with ZipFile(bundle) as zf:
            env=json.loads(zf.read("environment.json").decode("utf-8"))
        self.assertEqual(env["workspace_hash"],"redacted")

    def test_terminal_cli_json_and_markdown_modes(self):
        python=sys.executable
        base=[python,"-m","ucg.cli","--root",str(self.root)]
        for args in (["tree"],["outline","src/config.py"],["hotspots","--min-lines","50"],
                     ["repo-map","--focus","config"],["diff"],["brief"]):
            with self.subTest(command=args[0]):
                cp=subprocess.run(base+args,cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  encoding="utf-8",text=True,timeout=20)
                self.assertEqual(cp.returncode,0,cp.stderr)
                self.assertIsInstance(json.loads(cp.stdout or ""),dict)
        cp=subprocess.run(base+["brief","--format","markdown"],cwd=REPO,
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE,encoding="utf-8",text=True,timeout=20)
        self.assertEqual(cp.returncode,0,cp.stderr)
        self.assertTrue((cp.stdout or "").startswith("# Engineering Guardian"))


class PublicPrivacyTests(unittest.TestCase):
    def test_public_repository_has_generic_examples(self):
        forbidden=[
            re.compile(r"(?i)/Volumes/[^/\s]+/"),
            re.compile(r"(?i)/mnt/data/"),
            re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s]+"),
            re.compile(r"(?i)/Users/[^/\s]+/"),
            re.compile(r"(?i)https?://github\.com/[^/\s)]+/Engineering-Guardian"),
        ]
        # Don't scan .git or generated private diagnostics. Source control lists
        # precisely the text files that would be published.
        try:
            result=subprocess.run(["git","ls-files"],cwd=REPO,text=True,encoding="utf-8",
                                  capture_output=True,timeout=10,check=True)
            paths=[REPO/p for p in result.stdout.splitlines()]
        except (OSError,subprocess.SubprocessError):
            paths=[p for p in REPO.rglob("*") if ".git" not in p.parts and ".venv" not in p.parts]
        bad=[]
        for path in paths:
            if not path.is_file() or path.suffix.lower() not in (".md",".json",".toml",".py",".ps1",".sh",".cmd",".yml",".yaml",".cjs",".command",""):
                continue
            try:
                txt=path.read_text(encoding="utf-8")
            except (UnicodeError,OSError):
                continue
            for index,line in enumerate(txt.splitlines(),1):
                # Exclude the privacy regression test's own regex definitions.
                if path.name=="test_offline_privacy.py":
                    continue
                for pattern in forbidden:
                    if pattern.search(line):
                        bad.append(f"{path.relative_to(REPO)}:{index}")
        self.assertEqual(bad,[],f"Identifying or machine-specific paths in tracked files: {bad}")

    def test_benchmark_json_no_absolute_source_root(self):
        for file in (REPO/"reports").glob("*.json"):
            with self.subTest(report=file.name):
                value=json.loads(file.read_text(encoding="utf-8"))
                self.assertIsInstance(value,dict)
                self.assertNotIn("/mnt/data/",json.dumps(value))


if __name__=="__main__":
    unittest.main()
