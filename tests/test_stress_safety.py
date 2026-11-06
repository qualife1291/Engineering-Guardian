"""Safety and bounded-resource regressions for hostile or unusually large workspaces."""
from __future__ import annotations
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from ucg.engine import scan_workspace
from ucg.models import EdgeRecord, FileRecord, SymbolRecord
from ucg.scanner import MAX_FILE_BYTES, scan_files
from ucg.store import UCGStore

class WorkspaceScaleSafetyTests(unittest.TestCase):
    def test_hundreds_of_files_and_five_thousand_line_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"monorepo"; root.mkdir()
            for i in range(120):
                folder=root/f"package_{i//10:02d}"; folder.mkdir(exist_ok=True)
                body="\n".join([f"# generated line {n}" for n in range(39)]+[f"def module_{i}(): return {i}"])+"\n"
                (folder/f"module_{i}.py").write_text(body,encoding="utf-8")
            (root/"large_module.py").write_text(
                "\n".join(f"def generated_function_{i}(): return {i}" for i in range(5000))+"\n",
                encoding="utf-8")
            result=scan_workspace(str(root),str(Path(tmp)/"guardian"/"index.sqlite"))
            self.assertEqual(result["overview"]["files"],121)
            self.assertEqual(result["overview"]["lines"],120*40+5000)
            self.assertEqual(result["parsed_files"],121)
            self.assertGreaterEqual(result["overview"]["symbols"],5120)

    def test_oversized_file_is_skipped_before_unbounded_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"small.py").write_text("def ok(): return 1\n",encoding="utf-8")
            (root/"oversized.py").write_bytes(b"#"*(MAX_FILE_BYTES+1))
            records,skipped=scan_files(root)
            self.assertEqual([x.path for x in records],["small.py"])
            self.assertIn({"path":"oversized.py","reason":"max_file_size"},skipped)

    def test_fifo_is_skipped_without_blocking(self):
        if not hasattr(os, "mkfifo"):
            self.skipTest("FIFO special files are not supported on this platform")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            os.mkfifo(root/"pipe.py")
            records,skipped=scan_files(root)
            self.assertEqual(records,[])
            self.assertIn({"path":"pipe.py","reason":"non_regular_file"},skipped)

    def test_symlink_file_and_directory_cycle_are_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"root"; root.mkdir()
            (root/"real.py").write_text("def real(): return 1\n",encoding="utf-8")
            external=Path(tmp)/"external.py"
            external.write_text("def external(): return 2\n",encoding="utf-8")
            try:
                (root/"alias.py").symlink_to(external)
                (root/"loop").symlink_to(root,target_is_directory=True)
            except (OSError,NotImplementedError):
                self.skipTest("Symlinks are not permitted on this runner")
            records,skipped=scan_files(root)
            self.assertEqual([x.path for x in records],["real.py"])
            self.assertIn({"path":"alias.py","reason":"symlink"},skipped)
            self.assertNotIn("loop/real.py",[x.path for x in records])

    def test_concurrent_identical_scans_commit_one_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"shared"; root.mkdir()
            for i in range(30):
                (root/f"module_{i}.py").write_text(
                    f"def function_{i}(): return {i}\n",encoding="utf-8")
            db=Path(tmp)/"guardian"/"shared.sqlite"
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda _:scan_workspace(str(root),str(db)),range(2)))
            self.assertEqual(results[0]["snapshot_id"],results[1]["snapshot_id"])
            store=UCGStore(db)
            self.assertEqual(store.conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0],1)
            self.assertEqual(store.overview(results[0]["snapshot_id"])["files"],30)
            store.close()

    def test_graph_traversal_is_bounded_and_cycle_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=UCGStore(Path(tmp)/"index.sqlite")
            store.create_snapshot("graph",tmp)
            store.save_inventory("graph",[FileRecord("graph.py","python",1,1,"hash")])
            count=250
            symbols=[SymbolRecord(f"graph.py:f{i}:{i+1}",f"f{i}",f"f{i}","function",
                "graph.py","python",i+1,i+1,"def f(): pass") for i in range(count)]
            store.save_symbols("graph",symbols)
            edges=[EdgeRecord(symbols[i].symbol_id,symbols[i+1].symbol_id,"CALLS","test","graph.py",i+1)
                   for i in range(count-1)]
            edges.append(EdgeRecord(symbols[-1].symbol_id,symbols[0].symbol_id,"CALLS","test","graph.py",count))
            edges.extend(EdgeRecord(symbols[0].symbol_id,symbols[i].symbol_id,"CALLS","test","graph.py",1)
                         for i in range(1,count))
            store.save_edges("graph",edges)
            bounded=store.traverse("graph",symbols[0].symbol_id,"forward",10,20,17)
            self.assertLessEqual(len(bounded),17)
            self.assertTrue(all(x["depth"]<=10 for x in bounded))
            cycle=store.traverse("graph",symbols[0].symbol_id,"forward",20,300,1000)
            self.assertLessEqual(len(cycle),len(edges))
            store.close()

if __name__=="__main__":
    unittest.main()
