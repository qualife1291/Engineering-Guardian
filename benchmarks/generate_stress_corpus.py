"""Deterministic polyglot project generator for scale, topology and failure testing."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

LANGS = [
    ("python", ".py"), ("typescript", ".ts"), ("javascript", ".js"),
    ("java", ".java"), ("kotlin", ".kt"), ("dart", ".dart"),
    ("go", ".go"), ("rust", ".rs"), ("sql", ".sql"), ("protobuf", ".proto"),
]
COMMENT = {
    "python":"#", "typescript":"//", "javascript":"//", "java":"//",
    "kotlin":"//", "dart":"//", "go":"//", "rust":"//",
    "sql":"--", "protobuf":"//",
}


def _layout(root: Path, topology: str, index: int, language: str, files: int):
    if topology == "monolith":
        group = language
        folder = root / "src" / language
    elif topology == "microservices":
        service = index // 20
        group = f"service_{service:04d}:{language}"
        folder = root / "services" / f"service_{service:04d}" / "src" / language
    else:
        app = index % 5
        group = f"app_{app}:{language}"
        folder = root / "apps" / f"app_{app}" / "src" / language
    return group, folder


def _source(language: str, name: str, dep_name: str | None,
            dep_function: str | None, function_count: int, dynamic: bool,
            duplicate: bool) -> list[str]:
    out: list[str] = []
    if language == "python":
        if dep_name and dep_function:
            out.append(f"from .{dep_name} import {dep_function} as dependency")
        out += [f"def normalize_{name}(value):", "    return value.strip() if isinstance(value, str) else value", ""]
        for n in range(function_count):
            out += [f"def operation_{name}_{n}(value, client=None):",
                    f"    normalized = normalize_{name}(value)"]
            if dep_function:
                out.append("    normalized = dependency(normalized)")
            if dynamic:
                out.append("    if client is not None: client.send(normalized)")
            out += ["    return normalized", ""]
        if duplicate:
            out += [f"def normalize_{name}(value):", "    return value", ""]
    elif language in {"typescript", "javascript"}:
        if dep_name and dep_function:
            out.append(f'import {{ {dep_function} as dependency }} from "./{dep_name}";')
        typ = ": string" if language == "typescript" else ""
        ret = ": string" if language == "typescript" else ""
        out += [f"export function normalize_{name}(value{typ}){ret} {{ return value.trim(); }}", ""]
        for n in range(function_count):
            out += [f"export function operation_{name}_{n}(value{typ}){ret} {{",
                    f"  let normalized = normalize_{name}(value);"]
            if dep_function:
                out.append("  normalized = dependency(normalized);")
            if dynamic:
                out.append("  const client: any = (globalThis as any).client; if (client) client.send(normalized);"
                           if language == "typescript" else
                           "  const client = globalThis.client; if (client) client.send(normalized);")
            out += ["  return normalized;", "}", ""]
        if duplicate:
            out += [f"export function normalize_{name}(value{typ}){ret} {{ return value; }}", ""]
    elif language == "java":
        cls = "Module" + name
        out += [f"package bench.generated;", f"public class {cls} {{",
                f"  public String normalize_{name}(String value) {{ return value.trim(); }}"]
        for n in range(function_count):
            out += [f"  public String operation_{name}_{n}(String value) {{",
                    f"    return normalize_{name}(value);", "  }"]
        out += ["}"]
    elif language == "kotlin":
        cls = "Module" + name
        out += [f"package bench.generated", f"class {cls} {{",
                f"  fun normalize_{name}(value: String): String = value.trim()"]
        for n in range(function_count):
            out += [f"  fun operation_{name}_{n}(value: String): String {{",
                    f"    return normalize_{name}(value)", "  }"]
        out += ["}"]
    elif language == "dart":
        cls = "Module" + name
        out += [f"library module_{name};", f"class {cls} {{",
                f"  String normalize_{name}(String value) => value.trim();"]
        for n in range(function_count):
            out += [f"  String operation_{name}_{n}(String value) {{",
                    f"    return normalize_{name}(value);", "  }"]
        out += ["}"]
    elif language == "go":
        out += ["package generated",
                f"func Normalize{name}(value string) string {{ return value }}"]
        for n in range(function_count):
            out += [f"func Operation{name}_{n}(value string) string {{",
                    f"    return Normalize{name}(value)", "}"]
    elif language == "rust":
        out += [f"pub fn normalize_{name}(value: &str) -> String {{ value.trim().to_string() }}"]
        for n in range(function_count):
            out += [f"pub fn operation_{name}_{n}(value: &str) -> String {{",
                    f"    normalize_{name}(value)", "}"]
    elif language == "sql":
        out += [f"CREATE TABLE IF NOT EXISTS table_{name} (",
                "  id INTEGER PRIMARY KEY,", "  tenant_id INTEGER NOT NULL,",
                "  status TEXT NOT NULL,", "  payload TEXT", ");"]
        for n in range(function_count):
            out += [f"CREATE INDEX IF NOT EXISTS idx_{name}_{n} ON table_{name}(tenant_id, status);"]
    elif language == "protobuf":
        out += ['syntax = "proto3";', f"package bench.generated;",
                f"message Message{name} {{", "  string value = 1;", "  int64 id = 2;", "}"]
    return out


def _pad(lines: list[str], language: str, target: int, invalid: bool = False) -> list[str]:
    if invalid:
        bad = "def deliberately_broken(:"
        if language in {"typescript", "javascript"}:
            bad = "export function deliberatelyBroken( {"
        elif language == "java":
            bad = "public void deliberatelyBroken( {"
        elif language == "kotlin":
            bad = "fun deliberatelyBroken( {"
        elif language == "dart":
            bad = "void deliberatelyBroken( {"
        elif language == "go":
            bad = "func deliberatelyBroken( {"
        elif language == "rust":
            bad = "pub fn deliberately_broken( {"
        elif language == "sql":
            bad = "CREATE TABLE deliberately_broken ("
        elif language == "protobuf":
            bad = "message DeliberatelyBroken { string value = ;"
        if len(lines) >= target:
            lines[target - 1] = bad
        else:
            lines.append(bad)
    if len(lines) > target:
        raise ValueError(f"Generated {len(lines)} lines for {language}, target is {target}")
    prefix = COMMENT[language]
    while len(lines) < target:
        lines.append(f"{prefix} deterministic stress padding line {len(lines) + 1}")
    return lines


def _safe_reset(path: Path):
    resolved = path.expanduser().resolve()
    if resolved in {Path("/"), Path.home().resolve(), Path.cwd().resolve()}:
        raise ValueError("Refusing to reset a filesystem root, home directory or current directory")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--files", type=int, default=100)
    parser.add_argument("--lines", type=int, default=1000)
    parser.add_argument("--topology", choices=("monolith","microservices","monorepo"), default="monorepo")
    parser.add_argument("--large-file-lines", type=int, default=0)
    parser.add_argument("--functions-per-file", type=int, default=4)
    parser.add_argument("--invalid-every", type=int, default=0)
    parser.add_argument("--duplicate-every", type=int, default=0)
    parser.add_argument("--dynamic-every", type=int, default=0)
    parser.add_argument("--symlink-loop", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.files < 1 or args.lines < 10 or args.large_file_lines < 0 or args.functions_per_file < 0:
        raise SystemExit("files >= 1, lines >= 10, large-file-lines >= 0 and functions-per-file >= 0 are required")
    root = Path(args.output).expanduser()
    if root.exists():
        if not args.force:
            raise SystemExit("Output exists; pass --force to replace it")
        _safe_reset(root)
    else:
        root.mkdir(parents=True, exist_ok=True)

    entries = []
    group_items = {}
    for index in range(args.files):
        language, extension = LANGS[index % len(LANGS)]
        group, folder = _layout(root, args.topology, index, language, args.files)
        module_index = len(group_items.setdefault(group, []))
        stem = f"module_{module_index:05d}"
        path = folder / f"{stem}{extension}"
        group_items[group].append({"path":path,"stem":stem,"function":f"normalize_{index:05d}",
                                   "language":language,"index":index})
        entries.append({"path":path,"language":language,"group":group,"module_index":module_index,
                        "global_index":index})

    for group, items in group_items.items():
        for position, item in enumerate(items):
            target = items[(position - 1) % len(items)] if len(items) > 1 else None
            language = item["language"]
            dep_name = target["stem"] if target and language in {"python","typescript","javascript"} else None
            dep_function = target["function"] if dep_name else None
            index = item["index"]
            lines = _source(
                language, f"{index:05d}", dep_name, dep_function,
                args.functions_per_file,
                bool(args.dynamic_every and (index + 1) % args.dynamic_every == 0),
                bool(args.duplicate_every and (index + 1) % args.duplicate_every == 0))
            invalid = bool(args.invalid_every and (index + 1) % args.invalid_every == 0)
            source = _pad(lines, language, args.lines, invalid)
            item["path"].parent.mkdir(parents=True, exist_ok=True)
            item["path"].write_text("\n".join(source) + "\n", encoding="utf-8")

    large_path = None
    if args.large_file_lines:
        if args.large_file_lines < 2:
            raise SystemExit("large-file-lines must be 0 or at least 2")
        large_path = root / "stress" / "large_module.py"
        large_path.parent.mkdir(parents=True, exist_ok=True)
        count = args.large_file_lines // 2
        large = []
        for index in range(count):
            large += [f"def large_function_{index}(value):", "    return value"]
        while len(large) < args.large_file_lines:
            large.append(f"# large-file padding line {len(large) + 1}")
        large_path.write_text("\n".join(large) + "\n", encoding="utf-8")
        entries.append({"path":large_path,"language":"python","group":"stress-large-file",
                        "module_index":0,"global_index":args.files})

    manifest = {
        "generator":"engineering-guardian-stress-corpus-v1",
        "topology":args.topology,"source_files":len(entries),
        "small_files":args.files,"lines_per_small_file":args.lines,
        "large_file_lines":args.large_file_lines,
        "invalid_every":args.invalid_every,"duplicate_every":args.duplicate_every,
        "dynamic_every":args.dynamic_every,
        "languages":{language:sum(1 for e in entries if e["language"]==language) for language,_ in LANGS},
        "files":[{"path":e["path"].relative_to(root).as_posix(),"language":e["language"],
                  "group":e["group"],"lines":args.large_file_lines if e["path"]==large_path else args.lines}
                 for e in entries],
    }
    (root / "guardian_stress_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    if args.symlink_loop:
        try:
            (root / "stress" / "symlink-loop").symlink_to(root, target_is_directory=True)
        except (OSError, NotImplementedError):
            manifest["symlink_loop_created"] = False
        else:
            manifest["symlink_loop_created"] = True
        (root / "guardian_stress_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in manifest.items() if k!="files"},indent=2))


if __name__ == "__main__":
    main()
