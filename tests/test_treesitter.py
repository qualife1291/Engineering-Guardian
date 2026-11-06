"""Tree-sitter integration tests; CI installs grammars explicitly before running these."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from ucg.engine import scan_workspace
from ucg.service import GuardianService
from ucg.treesitter import (
    parser_available, parse_tree_sitter, resolve_references,
)


@unittest.skipUnless(parser_available("python"), "Tree-sitter Python grammar is not installed")
class TreeSitterPythonTests(unittest.TestCase):
    def test_python_symbols_import_alias_and_utf8_lines(self):
        provider = "def normalize(value):\n    return value.strip()\n"
        consumer = (
            "from provider import normalize as clean\n"
            "# unicode: café 🧪\n"
            "def caller(value):\n"
            "    return clean(value)\n"
        )
        a = parse_tree_sitter("provider.py", "python", provider)
        b = parse_tree_sitter("consumer.py", "python", consumer)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        symbols = a.symbols + b.symbols
        imports = resolve_references(Path("."), symbols, b.imports, b.references,
                                     a.symbol_analysis + b.symbol_analysis)
        self.assertEqual([x.name for x in symbols], ["normalize", "caller"])
        self.assertEqual(b.references[0].target_name, "clean")
        self.assertEqual(b.references[0].evidence_line, 4)
        self.assertEqual(b.references[0].resolution, "tree_sitter_import_binding")
        self.assertTrue(b.references[0].target_id.endswith("provider.py:normalize:1"))
        self.assertEqual(imports[0].resolved_path, "provider.py")
        self.assertEqual(b.file_analysis.parser_backend, "tree_sitter")

    def test_deeply_nested_source_does_not_use_python_recursion(self):
        source = "def deep():\n    return " + "(" * 1200 + "1" + ")" * 1200 + "\n"
        parsed = parse_tree_sitter("deep.py", "python", source)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.symbols[0].name, "deep")

    def test_dynamic_dispatch_stays_unresolved_and_syntax_errors_are_reported(self):
        source = (
            "def caller(client, value):\n"
            "    return client.send(value)\n"
            "\n"
            "def broken(:\n"
            "    return 1\n"
        )
        parsed = parse_tree_sitter("dynamic.py", "python", source)
        self.assertIsNotNone(parsed)
        self.assertGreater(parsed.file_analysis.error_count, 0)
        resolve_references(Path("."), parsed.symbols, parsed.imports,
                           parsed.references, parsed.symbol_analysis)
        self.assertTrue(parsed.references)
        self.assertEqual(parsed.references[0].resolution, "unresolved")
        self.assertIn("Receiver type is not known", parsed.references[0].reason)

    def test_self_method_binding_and_ambiguous_same_file_stays_unresolved(self):
        source = (
            "class Service:\n"
            "    def start(self):\n"
            "        return self.stop()\n"
            "    def stop(self):\n"
            "        return True\n"
        )
        parsed = parse_tree_sitter("service.py", "python", source)
        self.assertIsNotNone(parsed)
        resolve_references(Path("."), parsed.symbols, parsed.imports,
                           parsed.references, parsed.symbol_analysis)
        self.assertEqual(parsed.references[0].target_name, "stop")
        self.assertEqual(parsed.references[0].resolution, "tree_sitter_same_class")
        self.assertEqual(parsed.references[0].confidence, 0.85)

        ambiguous = (
            "def execute(): return 1\n"
            "def execute(): return 2\n"
            "def caller(): return execute()\n"
        )
        parsed2 = parse_tree_sitter("ambiguous.py", "python", ambiguous)
        resolve_references(Path("."), parsed2.symbols, parsed2.imports,
                           parsed2.references, parsed2.symbol_analysis)
        self.assertEqual(parsed2.references[0].resolution, "unresolved")
        self.assertIn("Multiple same-file", parsed2.references[0].reason)


@unittest.skipUnless(parser_available("typescript"), "Tree-sitter TypeScript grammar is not installed")
class TreeSitterTypeScriptTests(unittest.TestCase):
    def test_typescript_named_import_alias(self):
        provider = "export function normalize(value: string): string { return value.trim(); }\n"
        consumer = (
            'import { normalize as clean } from "./provider";\n'
            "export function caller(value: string): string { return clean(value); }\n"
        )
        a = parse_tree_sitter("provider.ts", "typescript", provider)
        b = parse_tree_sitter("consumer.ts", "typescript", consumer)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        symbols = a.symbols + b.symbols
        resolve_references(Path("."), symbols, b.imports, b.references,
                           a.symbol_analysis + b.symbol_analysis)
        self.assertTrue(any(x.name == "normalize" for x in a.symbols))
        self.assertTrue(any(x.name == "caller" for x in b.symbols))
        self.assertEqual(b.references[0].resolution, "tree_sitter_import_binding")
        self.assertTrue(b.references[0].target_id.endswith("provider.ts:normalize:1"))


@unittest.skipUnless(parser_available("python"), "Tree-sitter Python grammar is not installed")
class TreeSitterPolyglotSmokeTests(unittest.TestCase):
    def test_all_advertised_grammars_parse_a_minimal_valid_file(self):
        examples = {
            "python": "def normalize(value):\n    return value.strip()\n",
            "typescript": "export function normalize(value: string): string { return value.trim(); }\n",
            "javascript": "export function normalize(value) { return value.trim(); }\n",
            "java": "package bench; public class Sample { public String normalize(String value) { return value.trim(); } }\n",
            "kotlin": "class Sample { fun normalize(value: String): String = value.trim() }\n",
            "dart": "class Sample { String normalize(String value) => value.trim(); }\n",
            "go": "package bench\nfunc Normalize(value string) string { return value }\n",
            "rust": "pub fn normalize(value: &str) -> String { value.to_string() }\n",
            "sql": "CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT);\n",
            "protobuf": 'syntax = "proto3"; package bench; message Sample { string value = 1; }\n',
        }
        for language, source in examples.items():
            with self.subTest(language=language):
                self.assertTrue(parser_available(language), f"{language} grammar was requested in CI but is missing")
                parsed = parse_tree_sitter(f"sample.{language}", language, source)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.file_analysis.parser_backend, "tree_sitter")
                self.assertEqual(parsed.file_analysis.parse_status, "ok",
                                 f"{language} parse errors: {parsed.file_analysis.error_count}")


@unittest.skipUnless(parser_available("python"), "Tree-sitter Python grammar is not installed")
class ChangeXRayTests(unittest.TestCase):
    def test_change_xray_finds_callers_and_affected_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "sample-app"
            tests = root / "tests"
            tests.mkdir(parents=True)
            (root / "provider.py").write_text(
                "def normalize(value):\n    return value.strip()\n", encoding="utf-8")
            (root / "consumer.py").write_text(
                "from provider import normalize as clean\n"
                "def display(value):\n    return clean(value)\n", encoding="utf-8")
            (tests / "test_provider.py").write_text(
                "from provider import normalize\n"
                "def test_normalize():\n    return normalize(' value ')\n", encoding="utf-8")
            service = GuardianService(str(root), diagnostics=False)
            first = service.scan()
            (root / "provider.py").write_text(
                "def normalize(value):\n    return value.strip().lower()\n", encoding="utf-8")
            second = service.scan()
            impact = service.change_impact(first["snapshot_id"], second["snapshot_id"])
            self.assertEqual(impact["impact_status"], "analyzed")
            self.assertTrue(any(x["qualified_name"] == "normalize" and x["change"] == "body_changed"
                                for x in impact["changed_symbols"]))
            self.assertIn("tests/test_provider.py", impact["affected_tests"])
            self.assertTrue(any(x["qualified_name"] == "display"
                                for x in impact["direct_dependents"]))
            self.assertEqual(impact["static_resolution_confidence"], "higher_static_confidence")


if __name__ == "__main__":
    unittest.main()
