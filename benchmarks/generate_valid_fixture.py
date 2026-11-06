from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

LANGS = [("python", ".py"), ("typescript", ".ts"), ("kotlin", ".kt"), ("dart", ".dart"), ("sql", ".sql")]
TARGET_LINES = 1000

def pad_lines(lines: list[str], language: str, target: int = TARGET_LINES) -> list[str]:
    if len(lines) > target:
        raise ValueError(f"{language} generated {len(lines)} lines, exceeds target {target}")
    prefixes = {"python": "#", "typescript": "//", "kotlin": "//", "dart": "//", "sql": "--"}
    while len(lines) < target:
        n = len(lines) + 1
        lines.append(f"{prefixes[language]} deterministic valid padding line {n}")
    return lines

def python_source(base: str) -> list[str]:
    out = ["from typing import Any", "", f"MODULE = '{base}'", ""]
    for j in range(1, 11):
        out += [
            f"def normalize_{base}_{j}(value: Any) -> Any:",
            "    if value is None:", "        return {}",
            "    if isinstance(value, dict):", "        return dict(value)",
            "    return {'value': value}", "",
            f"def validate_{base}_{j}(value: Any) -> bool:",
            "    return value is not None", "",
            f"def persist_{base}_{j}(value: Any, context: dict) -> dict:",
            f"    context['stage'] = {j}", "    context['payload'] = value", "    return context", "",
        ]
    for j in range(1, 56):
        h = (j % 10) + 1
        out += [
            f"def {base}_operation_{j}(payload: Any, context: dict | None = None) -> dict:",
            "    state = dict(context or {})", "    if payload is None:", "        return state",
            f"    normalized = normalize_{base}_{h}(payload)",
            f"    if not validate_{base}_{h}(normalized):",
            "        raise ValueError('invalid payload')",
            f"    return persist_{base}_{h}(normalized, state)", "",
        ]
    return pad_lines(out, "python")

def typescript_source(base: str) -> list[str]:
    out = [f"export const MODULE = '{base}';", "", "export type Context = Record<string, unknown>;", ""]
    for j in range(1, 11):
        out += [
            f"export function normalize_{base}_{j}(value: unknown): unknown {{",
            "  if (value == null) return {};",
            "  if (typeof value === 'object') return { ...(value as object) };",
            "  return { value };", "}",
            f"export function validate_{base}_{j}(value: unknown): boolean {{ return value !== undefined; }}",
            f"export function persist_{base}_{j}(value: unknown, context: Context): Context {{ context.stage = {j}; context.payload = value; return context; }}", "",
        ]
    for j in range(1, 76):
        h = (j % 10) + 1
        out += [
            f"export function {base}_operation_{j}(payload: unknown, context: Context = {{}}): Context {{",
            f"  const normalized = normalize_{base}_{h}(payload);",
            f"  if (!validate_{base}_{h}(normalized)) throw new Error('invalid payload');",
            f"  return persist_{base}_{h}(normalized, context);", "}", "",
        ]
    return pad_lines(out, "typescript")

def kotlin_source(base: str) -> list[str]:
    class_name = ''.join(p.title() for p in base.split('_')) + "Service"
    out = [f"package generated.{base}", "", f"class {class_name} {{"]
    for j in range(1, 11):
        out += [
            f"    private fun normalize{j}(value: Any?): Any? {{",
            "        if (value == null) return emptyMap<String, Any>()", "        return value", "    }",
            f"    private fun validate{j}(value: Any?): Boolean = value != null",
            f"    private fun persist{j}(value: Any?, context: MutableMap<String, Any?>): Any? {{ context[\"stage\"] = {j}; context[\"payload\"] = value; return context }}", "",
        ]
    for j in range(1, 76):
        h = (j % 10) + 1
        out += [
            f"    fun operation{j}(payload: Any?, context: MutableMap<String, Any?> = mutableMapOf()): Any? {{",
            f"        val normalized = normalize{h}(payload)",
            f"        if (!validate{h}(normalized)) throw IllegalArgumentException(\"invalid payload\")",
            f"        return persist{h}(normalized, context)", "    }", "",
        ]
    out += ["}"]
    return pad_lines(out, "kotlin")

def dart_source(base: str) -> list[str]:
    class_name = ''.join(p.title() for p in base.split('_')) + "Service"
    out = [f"library {base};", "", f"class {class_name} {{"]
    for j in range(1, 11):
        out += [
            f"  Object? normalize{j}(Object? value) {{",
            "    if (value == null) return <String, Object?>{};", "    return value;", "  }",
            f"  bool validate{j}(Object? value) {{ return value != null; }}",
            f"  Object? persist{j}(Object? value, Map<String, Object?> context) {{ context['stage'] = {j}; context['payload'] = value; return context; }}", "",
        ]
    for j in range(1, 76):
        h = (j % 10) + 1
        out += [
            f"  Object? operation{j}(Object? payload, [Map<String, Object?>? context]) {{",
            "    final state = context ?? <String, Object?>{};",
            f"    final normalized = normalize{h}(payload);",
            f"    if (!validate{h}(normalized)) throw ArgumentError('invalid payload');",
            f"    return persist{h}(normalized, state);", "  }", "",
        ]
    out += ["}"]
    return pad_lines(out, "dart")

def sql_source(base: str) -> list[str]:
    out = [f"-- Valid SQL benchmark module {base}", "BEGIN TRANSACTION;", ""]
    for j in range(1, 56):
        out += [
            f"CREATE TABLE IF NOT EXISTS {base}_table_{j} (",
            "    id INTEGER PRIMARY KEY,", "    tenant_id INTEGER NOT NULL,",
            "    status TEXT NOT NULL,", "    payload TEXT,", "    created_at TEXT NOT NULL,",
            "    version INTEGER NOT NULL DEFAULT 1", ");",
            f"CREATE INDEX IF NOT EXISTS idx_{base}_{j}_tenant_status ON {base}_table_{j}(tenant_id, status);", "",
        ]
    out += ["COMMIT;"]
    return pad_lines(out, "sql")

BUILDERS = {"python": python_source, "typescript": typescript_source, "kotlin": kotlin_source, "dart": dart_source, "sql": sql_source}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    p.add_argument("--files", type=int, default=100)
    p.add_argument("--lines", type=int, default=1000)
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    if a.lines != TARGET_LINES:
        raise SystemExit("This validation fixture currently targets exactly 1,000 lines per source file.")
    root = Path(a.output)
    if root.exists() and a.force:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = []
    for i in range(a.files):
        lang, ext = LANGS[i % len(LANGS)]
        module = i // 10
        base = f"{lang}_{i:03d}"
        nested = root / f"domain_{module % 5:02d}" / f"layer_{module // 5:02d}" / f"module_{module:02d}"
        nested.mkdir(parents=True, exist_ok=True)
        path = nested / f"{base}{ext}"
        source = BUILDERS[lang](base)
        if len(source) != a.lines:
            raise AssertionError((path, len(source)))
        path.write_text("\n".join(source) + "\n", encoding="utf-8")
        manifest.append({"path": path.relative_to(root).as_posix(), "language": lang, "lines": a.lines, "module": module})
    (root / "benchmark_manifest.json").write_text(json.dumps({"files": manifest, "expected_source_files": a.files, "lines_per_file": a.lines, "syntax_validity": "validated separately per available compiler/parser"}, indent=2))
    print(json.dumps({"root": str(root.resolve()), "source_files": a.files, "lines_per_file": a.lines, "total_lines": a.files * a.lines, "languages": {k: sum(1 for x in manifest if x['language'] == k) for k, _ in LANGS}}, indent=2))

if __name__ == "__main__":
    main()
