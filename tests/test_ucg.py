import tempfile, unittest
from pathlib import Path
from ucg.scanner import scan_files
from ucg.parser import parse_file
from ucg.engine import scan_workspace
from ucg.store import UCGStore
from ucg.context import build_context_pack
from ucg.treesitter import parser_available

class UCGTests(unittest.TestCase):
    def test_scan_non_git_folder(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"nested"/"sample.py";p.parent.mkdir();p.write_text("def alpha():\n    return 1\n")
            files,skipped=scan_files(d)
            self.assertEqual(len(files),1);self.assertEqual(files[0].language,"python")
    def test_sensitive_and_symlink_files_are_skipped(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root=Path(d)
            (root/"main.py").write_text("def main():\n    return 1\n")
            (root/".env").write_text("TOKEN=do-not-index\n")
            (root/"private.key").write_text("secret\n")
            external=Path(outside)/"external.py"
            external.write_text("def external():\n    return 2\n")
            try:
                (root/"linked.py").symlink_to(external)
            except OSError:
                pass
            files,skipped=scan_files(root)
            paths={f.path for f in files}
            self.assertIn("main.py",paths)
            self.assertNotIn(".env",paths)
            self.assertNotIn("private.key",paths)
            self.assertTrue(any(x["reason"]=="sensitive_file" for x in skipped))

    def test_python_ast_symbols(self):
        symbols=parse_file("a.py","python","class A:\n    def run(self, x):\n        return x\n")
        self.assertEqual({s.name for s in symbols},{"A","run"})
    def test_polyglot_structural_extraction(self):
        samples={
            "typescript":("a.ts","export function renderVideo(input: unknown) { return input; }"),
            "kotlin":("a.kt","class RenderService { fun renderVideo(input: Any): Any { return input } }"),
            "dart":("a.dart","class RenderService { Future<Object?> renderVideo(Object? input) async { return input; } }"),
            "sql":("a.sql","CREATE TABLE IF NOT EXISTS videos (id INTEGER PRIMARY KEY);"),
        }
        for language,(path,source) in samples.items():
            with self.subTest(language=language):
                symbols=parse_file(path,language,source)
                self.assertTrue(symbols)

    def test_unique_cross_file_call_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "src"
            root.mkdir()
            (root / "consumer.py").write_text(
                "from provider import shared_normalize\n\n"
                "def caller(payload):\n    return shared_normalize(payload)\n"
            )
            (root / "provider.py").write_text(
                "def shared_normalize(payload):\n    return payload or {}\n"
            )
            db = Path(d) / "cross.sqlite"
            scan_workspace(str(root), str(db), "cross")
            store = UCGStore(db)
            caller = store.search("cross", "caller")[0]
            edges = store.traverse("cross", caller["symbol_id"], "forward", max_depth=1)
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0]["evidence_path"], "consumer.py")
            self.assertIn("provider.py", edges[0]["to"])
            expected_resolution = "tree_sitter_import_binding" if parser_available("python") else "ast_candidate"
            self.assertEqual(edges[0]["resolution"], expected_resolution)
            store.close()

    def test_dart_nullable_object_return_type(self):
        source = "class VideoService {\n  Object? normalize(Object? value) { return value; }\n}"
        symbols = parse_file("video.dart", "dart", source)
        self.assertIn("VideoService", {s.name for s in symbols})
        self.assertIn("normalize", {s.name for s in symbols})

    def test_scan_persists_graph(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"src";root.mkdir()
            (root/"a.py").write_text("def target():\n    return 1\n\ndef caller():\n    return target()\n")
            result=scan_workspace(str(root),str(Path(d)/"idx.sqlite"),"s1")
            self.assertEqual(result["overview"]["files"],1)
            self.assertGreaterEqual(result["overview"]["symbols"],2)
            self.assertGreaterEqual(result["overview"]["edges"],1)
            store=UCGStore(Path(d)/"idx.sqlite")
            hits=store.search("s1","caller")
            self.assertTrue(hits)
            self.assertEqual(hits[0]["name"], "caller")
            self.assertTrue(store.search("s1", "all"))  # substring fallback
            forward=store.traverse("s1",hits[0]["symbol_id"],"forward",max_depth=2)
            self.assertTrue(forward)
            store.close()
            pack=build_context_pack(str(Path(d)/"idx.sqlite"),"s1","caller")
            self.assertGreaterEqual(len(pack["symbols"]),1)
            self.assertIn("def caller",pack["symbols"][0]["snippet"])

if __name__=="__main__":unittest.main()
