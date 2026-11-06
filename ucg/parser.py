from __future__ import annotations
import ast
import re
from pathlib import Path
from .models import SymbolRecord

PY_CALL_SKIP = {"if", "for", "while", "with", "return", "yield", "assert", "print"}
PATTERNS = {
    "typescript": [
        ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
        ("interface", re.compile(r"\binterface\s+([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
        ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
        ("method", re.compile(r"^\s{2,}(?:async\s+)?([A-Za-z_$][\w$]*)\s*\([^;]*\)\s*:\s*[^=]+\{" , re.M)),
    ],
    "javascript": [
        ("class", re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")),
        ("function", re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(")),
        ("function", re.compile(r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>")),
    ],
    "dart": [
        ("class", re.compile(r"\bclass\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"(?:^|\s)(?:Future<[^>]+>|void|String|int|bool|dynamic|Object\??|[A-Z]\w*(?:<[^>]+>)?\??)\s+([a-zA-Z_]\w*)\s*\([^;]*\)\s*(?:async\s*)?\{")),
    ],
    "kotlin": [
        ("class", re.compile(r"\bclass\s+([A-Za-z_]\w*)")),
        ("interface", re.compile(r"\binterface\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"\bfun\s+(?:<[^>]+>\s*)?([A-Za-z_]\w*)\s*\(")),
    ],
    "java": [
        ("class", re.compile(r"\bclass\s+([A-Za-z_]\w*)")),
        ("interface", re.compile(r"\binterface\s+([A-Za-z_]\w*)")),
        ("function", re.compile(r"\b(?:public|private|protected|static|final|synchronized|\s)+[\w<>?,.\[\]]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{")),
    ],
    "sql": [
        ("table", re.compile(r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?([\w.]+)", re.I)),
        ("view", re.compile(r"\bCREATE\s+VIEW\s+[\"`]?([\w.]+)", re.I)),
        ("procedure", re.compile(r"\bCREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([\w.]+)", re.I)),
    ],
}

def _line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1

def _brace_end(lines: list[str], start_idx: int) -> int:
    depth = 0
    started = False
    for idx in range(start_idx, len(lines)):
        line = lines[idx]
        # Prototype only: brace counting does not fully understand strings/comments.
        depth += line.count("{") - line.count("}")
        if "{" in line: started = True
        if started and depth <= 0: return idx + 1
    return min(len(lines), start_idx + 1)

def parse_python(path: str, text: str) -> list[SymbolRecord]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    lines = text.splitlines()
    out = []
    def walk(body, prefix=""):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else "function"
                name = node.name
                qname = f"{prefix}.{name}" if prefix else name
                start = getattr(node, "lineno", 1)
                end = getattr(node, "end_lineno", start)
                sig = ""
                if kind == "function":
                    args = [a.arg for a in node.args.args]
                    sig = f"{name}({', '.join(args)})"
                else:
                    sig = f"class {name}"
                out.append(SymbolRecord(f"{path}:{qname}:{start}", name, qname, kind, path, "python", start, end, sig))
                if isinstance(node, ast.ClassDef): walk(node.body, qname)
    walk(tree.body)
    return out

def parse_structural(path: str, language: str, text: str) -> list[SymbolRecord]:
    lines = text.splitlines()
    out = []
    seen = set()
    for kind, pattern in PATTERNS.get(language, []):
        for match in pattern.finditer(text):
            name = match.group(1)
            start = _line_for_offset(text, match.start())
            key = (kind, name, start)
            if key in seen: continue
            seen.add(key)
            end = _brace_end(lines, start - 1) if language != "sql" else start
            sig_line = lines[start - 1].strip()[:240] if start <= len(lines) else name
            out.append(SymbolRecord(f"{path}:{name}:{start}", name, name, kind, path, language, start, end, sig_line))
    return out

def parse_file(path: str, language: str, text: str) -> list[SymbolRecord]:
    if language == "python": return parse_python(path, text)
    return parse_structural(path, language, text)

def extract_call_candidates(language: str, text: str, symbols: list[SymbolRecord]):
    # Candidate-only resolver. Exact semantic resolution belongs to SCIP/LSP adapters.
    definitions = {s.name for s in symbols if s.kind in {"function", "method"}}
    candidates = []
    for line_no, line in enumerate(text.splitlines(), 1):
        for name in definitions:
            if re.search(rf"(?<![\w.]){re.escape(name)}\s*\(", line):
                candidates.append((name, line_no))
    return candidates
