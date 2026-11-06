"""Regression tests for POC v0.3: snapshot isolation, reuse and MCP privacy."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ucg.context import StaleSnapshotError, build_context_pack
from ucg.engine import scan_workspace
from ucg.service import GuardianService
from ucg.diagnostics import support_bundle
from ucg.mcp import GuardianMCP
from ucg.store import UCGStore


class GuardianV03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)/"project"
        self.root.mkdir()
        self.data = Path(self.tmp.name)/"guardian-data"
        patcher = patch.dict(os.environ,{"GUARDIAN_HOME":str(self.data)})
        patcher.start(); self.addCleanup(patcher.stop)
        (self.root/"provider.py").write_text("def target():\n    return 7\n",encoding="utf-8")
        (self.root/"consumer.py").write_text("def caller():\n    return target()\n",encoding="utf-8")
        self.db = self.data/"idx.sqlite"

    def test_same_source_reuses_exact_snapshot(self):
        a=scan_workspace(str(self.root),str(self.db))
        with patch("ucg.engine.parse_file",side_effect=AssertionError("must not parse")):
            b=scan_workspace(str(self.root),str(self.db))
        self.assertEqual(a["snapshot_id"],b["snapshot_id"])
        self.assertTrue(b["cache_hit"])
        self.assertEqual(b["parsed_files"],0)
        s=UCGStore(self.db)
        self.assertEqual(s.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],1)
        s.close()

    def test_only_changed_file_reparsed_and_call_edges_preserved(self):
        a=scan_workspace(str(self.root),str(self.db))
        (self.root/"provider.py").write_text("def target():\n    return 8\n",encoding="utf-8")
        b=scan_workspace(str(self.root),str(self.db))
        self.assertFalse(b["cache_hit"])
        self.assertEqual(b["parsed_files"],1)
        self.assertEqual(b["reused_files"],1)
        s=UCGStore(self.db)
        caller=s.search(b["snapshot_id"],"caller")[0]
        edges=s.traverse(b["snapshot_id"],caller["symbol_id"],"forward",1)
        self.assertEqual(len(edges),1)
        self.assertTrue(edges[0]["to"].endswith("provider.py:target:1"))
        self.assertTrue(s.has_snapshot(a["snapshot_id"]))
        s.close()

    def test_stale_context_never_contains_new_source(self):
        a=scan_workspace(str(self.root),str(self.db))
        (self.root/"consumer.py").write_text("def caller():\n    return 'NEW_PRIVATE_SOURCE'\n",encoding="utf-8")
        with self.assertRaises(StaleSnapshotError):
            build_context_pack(str(self.db),a["snapshot_id"],"caller")
        service=GuardianService(str(self.root),str(self.db))
        self.assertEqual(service.status()["index_status"],"stale")
        with self.assertRaises(StaleSnapshotError):
            service.find_symbol("caller")

    def test_atomic_snapshot_when_source_changes_during_parse(self):
        from ucg.engine import SourceChangedDuringScan
        from ucg.parser import parse_file
        calls=[]
        def mutating_parse(path,lang,text):
            calls.append(path)
            if len(calls)==1:
                (self.root/"provider.py").write_text("def target():\n    return 999\n",encoding="utf-8")
            return parse_file(path,lang,text)
        with patch("ucg.engine.parse_file",side_effect=mutating_parse):
            with self.assertRaises(SourceChangedDuringScan):
                scan_workspace(str(self.root),str(self.db))
        s=UCGStore(self.db)
        self.assertEqual(s.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],0)
        s.close()

    def test_mcp_initialize_tools_and_scan(self):
        service=GuardianService(str(self.root),str(self.db))
        mcp=GuardianMCP(service)
        init=mcp.dispatch({"jsonrpc":"2.0","id":1,"method":"initialize",
                           "params":{"protocolVersion":"2025-06-18"}})
        self.assertEqual(init["result"]["protocolVersion"],"2025-06-18")
        tools=mcp.dispatch({"jsonrpc":"2.0","id":2,"method":"tools/list"})["result"]["tools"]
        self.assertIn("guardian_scan",[t["name"] for t in tools])
        scan=mcp.dispatch({"jsonrpc":"2.0","id":3,"method":"tools/call",
                          "params":{"name":"guardian_scan","arguments":{}}})
        self.assertFalse(scan["result"]["isError"])
        self.assertEqual(json.loads(scan["result"]["content"][0]["text"])["overview"]["files"],2)
        bad=mcp.dispatch({"jsonrpc":"2.0","id":4,"method":"tools/call",
                          "params":{"name":"guardian_scan","arguments":{"root":"/etc"}}})
        self.assertTrue(bad["result"]["isError"])
        self.assertIn("INVALID_ARGUMENT",bad["result"]["content"][0]["text"])
        self.assertFalse(mcp.dispatch({"jsonrpc":"2.0","method":"notifications/initialized"}))

    def test_stdio_protocol_has_no_non_json_output(self):
        program=Path(__file__).resolve().parents[1]/"scripts"/"guardian_mcp.py"
        reqs=[{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}},
              {"jsonrpc":"2.0","id":2,"method":"tools/list"},
              {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"guardian_index_status","arguments":{}}}]
        proc=subprocess.run([sys.executable,str(program),"--root",str(self.root)],
                            input="\n".join(json.dumps(r) for r in reqs)+"\n",text=True,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        lines=[json.loads(x) for x in proc.stdout.splitlines()]
        self.assertEqual(len(lines),3)
        self.assertEqual(lines[0]["id"],1)
        self.assertEqual(lines[1]["id"],2)
        self.assertEqual(lines[2]["id"],3)

    def test_diagnostics_bundle_excludes_paths_and_source(self):
        secret="PRIVATE_SUPER_SECRET_TOKEN_2026"
        (self.root/"provider.py").write_text("def target():\n    return '"+secret+"'\n",encoding="utf-8")
        service=GuardianService(str(self.root),str(self.db))
        result=service.scan()
        self.assertEqual(result["overview"]["files"],2)
        service.find_symbol("target")
        report=service.support_log()
        path=Path(report["bundle_path"])
        self.assertTrue(path.is_file())
        import zipfile
        with zipfile.ZipFile(path) as archive:
            data="\n".join(archive.read(n).decode() for n in archive.namelist())
        self.assertNotIn(secret,data)
        self.assertNotIn(str(self.root),data)
        self.assertNotIn("provider.py",data)
        self.assertNotIn("target",data)
        self.assertIn("cache_hit",data)

    def test_empty_query_and_max_context(self):
        service=GuardianService(str(self.root),str(self.db))
        service.scan()
        result=service.context("caller",512)
        self.assertLessEqual(result["context_characters"],512)
        self.assertEqual(result["snapshot_id"],service.status()["snapshot_id"])

    def test_py_utf8_and_secret_skipped(self):
        (self.root/".env.production").write_text("API_KEY=do-not-parse\n")
        (self.root/"id_ed25519").write_text("private data")
        service=GuardianService(str(self.root),str(self.db))
        result=service.scan()
        self.assertEqual(result["overview"]["files"],2)
        self.assertGreaterEqual(result["skipped_files"],2)

if __name__=="__main__":
    unittest.main()
