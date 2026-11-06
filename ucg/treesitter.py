"""Optional, offline-safe Tree-sitter syntax extraction and conservative local binding.

The language-pack registry is queried before a parser is requested. Scanning never
downloads grammars; downloads happen only through the explicit CLI install command.
Resolved edges describe a unique syntactic binding, not compiler/type-checker proof.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .models import (
    FileAnalysisRecord, ImportRecord, ReferenceRecord, SymbolAnalysisRecord, SymbolRecord,
)

PARSER_NAMES = {
    "python": "python", "typescript": "typescript", "javascript": "javascript",
    "dart": "dart", "kotlin": "kotlin", "java": "java", "sql": "sql",
    "go": "go", "rust": "rust", "protobuf": "proto",
}
CALL_TYPES = {
    "python": {"call"},
    "typescript": {"call_expression"}, "javascript": {"call_expression"},
    "java": {"method_invocation"}, "kotlin": {"call_expression"},
    "dart": {"method_invocation", "function_expression_invocation"},
    "go": {"call_expression"},
    "rust": {"call_expression", "method_call_expression"},
}
IMPORT_TYPES = {
    "python": {"import_statement", "import_from_statement"},
    "typescript": {"import_statement"}, "javascript": {"import_statement"},
    "java": {"import_declaration"}, "kotlin": {"import_header"},
    "dart": {"import_or_export"}, "go": {"import_spec"},
    "rust": {"use_declaration"},
}
DECLARATIONS = {
    "python": {"function_definition": "function", "class_definition": "class"},
    "typescript": {
        "function_declaration": "function", "generator_function_declaration": "function",
        "method_definition": "method", "class_declaration": "class",
        "abstract_class_declaration": "class", "interface_declaration": "interface",
        "type_alias_declaration": "type", "enum_declaration": "enum",
    },
    "javascript": {
        "function_declaration": "function", "generator_function_declaration": "function",
        "method_definition": "method", "class_declaration": "class",
    },
    "java": {
        "class_declaration": "class", "interface_declaration": "interface",
        "enum_declaration": "enum", "record_declaration": "class",
        "method_declaration": "method", "constructor_declaration": "method",
    },
    "kotlin": {
        "class_declaration": "class", "object_declaration": "class",
        "function_declaration": "function", "secondary_constructor": "method",
    },
    "dart": {
        "class_definition": "class", "mixin_declaration": "mixin",
        "enum_declaration": "enum", "extension_declaration": "extension",
        "function_declaration": "function", "method_signature": "method",
    },
    "go": {
        "function_declaration": "function", "method_declaration": "method",
        "type_spec": "type",
    },
    "rust": {
        "function_item": "function", "struct_item": "struct", "enum_item": "enum",
        "trait_item": "trait", "impl_item": "impl", "type_item": "type",
        "mod_item": "module",
    },
    "sql": {
        "create_table": "table", "create_view": "view",
        "create_function": "function", "create_procedure": "procedure",
    },
    "protobuf": {
        "message": "message", "service": "service", "enum": "enum", "rpc": "method",
    },
}
TYPE_SCOPES = {"class", "interface", "struct", "trait", "impl", "enum", "module", "namespace"}
CALLABLES = {"function", "method", "procedure"}
NAME_TYPES = {
    "identifier", "type_identifier", "simple_identifier", "field_identifier",
    "property_identifier", "namespace_identifier", "name",
}
BODY_TYPES = {
    "block", "block_statement", "function_body", "statement_block",
    "compound_statement", "class_body", "declaration_list",
}
ATTRIBUTE_TYPES = {
    "attribute", "member_expression", "selector_expression", "field_expression",
    "scoped_identifier", "navigation_expression", "qualified_identifier",
}
EXTS = (".py", ".pyi", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        ".java", ".kt", ".kts", ".dart", ".go", ".rs", ".sql", ".proto")


@dataclass(slots=True)
class ParseBundle:
    symbols: list[SymbolRecord]
    imports: list[ImportRecord]
    references: list[ReferenceRecord]
    file_analysis: FileAnalysisRecord
    symbol_analysis: list[SymbolAnalysisRecord]


def _version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _parser_name(language: str) -> str | None:
    return PARSER_NAMES.get(language)


def parser_registry():
    try:
        from tree_sitter_language_pack import LanguageRegistry
        return LanguageRegistry.new()
    except (ImportError, OSError, RuntimeError):
        return None


def parser_available(language: str) -> bool:
    name = _parser_name(language)
    if not name:
        return False
    registry = parser_registry()
    if registry is None:
        return False
    try:
        # has_language only checks compiled/cached grammars; it does not fetch.
        return bool(registry.has_language(name))
    except Exception:
        return False


def parser_status(languages: list[str] | None = None) -> dict:
    selected = languages or sorted(PARSER_NAMES)
    try:
        import tree_sitter  # noqa: F401
        from tree_sitter_language_pack import LanguageRegistry, downloaded_languages
        registry = LanguageRegistry.new()
        installed = []
        for lang in selected:
            name = _parser_name(lang)
            if name and registry.has_language(name):
                installed.append(lang)
        cached = sorted(set(downloaded_languages()))
        return {
            "optional_dependencies": True,
            "tree_sitter_version": _version("tree-sitter"),
            "language_pack_version": _version("tree-sitter-language-pack"),
            "supported_languages": selected,
            "installed_languages": installed,
            "missing_languages": [x for x in selected if x not in installed],
            "cached_grammar_names": cached,
            "automatic_download_during_scan": False,
        }
    except (ImportError, OSError, RuntimeError) as exc:
        return {
            "optional_dependencies": False,
            "tree_sitter_version": None,
            "language_pack_version": None,
            "supported_languages": selected,
            "installed_languages": [],
            "missing_languages": selected,
            "cached_grammar_names": [],
            "automatic_download_during_scan": False,
            "hint": "Install the optional treesitter extra, then run guardian parsers install.",
            "error_type": type(exc).__name__,
        }


def install_parsers(languages: list[str]) -> dict:
    selected = sorted(set(languages))
    unknown = sorted(set(selected) - set(PARSER_NAMES))
    if unknown:
        raise ValueError("Unsupported parser language: " + ", ".join(unknown))
    try:
        from tree_sitter_language_pack import download
    except ImportError as exc:
        raise RuntimeError("Install the optional extra: pip install 'engineering-guardian-ucg-poc[treesitter]'") from exc
    count = download([PARSER_NAMES[x] for x in selected])
    return {"requested_languages": selected, "available_count": count,
            "status": parser_status(selected),
            "notice": "Grammar downloads occur only because this install command was explicitly requested."}


def _kind(node) -> str:
    try:
        return node.type
    except Exception:
        return ""


def _start_byte(node) -> int:
    return int(node.start_byte)


def _end_byte(node) -> int:
    return int(node.end_byte)


def _start_row(node) -> int:
    return int(node.start_point.row)


def _end_row(node) -> int:
    return int(node.end_point.row)


def _children(node):
    try:
        return list(node.named_children)
    except Exception:
        return []


def _text(node, source: bytes) -> str:
    try:
        return source[_start_byte(node):_end_byte(node)].decode("utf-8", errors="replace")
    except Exception:
        return ""


def _field(node, *names):
    for name in names:
        try:
            value = node.child_by_field_name(name)
        except Exception:
            value = None
        if value is not None:
            return value
    return None


def _name_node(node):
    value = _field(node, "name", "method", "type")
    if value is not None and _kind(value) in NAME_TYPES | {"type_identifier"}:
        return value
    for child in _children(node):
        if _kind(child) in NAME_TYPES:
            return child
    return None


def _body_node(node):
    if node is None:
        return None
    value = _field(node, "body", "block", "function_body")
    if value is not None:
        return value
    for child in _children(node):
        if _kind(child) in BODY_TYPES:
            return child
    return None


def _hash(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def _signature(node, body, source: bytes) -> str:
    end = _start_byte(body) if body is not None else _end_byte(node)
    value = source[_start_byte(node):end].decode("utf-8", errors="replace")
    value = " ".join(value.strip().split())
    return value[:500]


def _normal_kind(language: str, raw_kind: str, scope_kinds: list[str]) -> str:
    if raw_kind == "function" and scope_kinds and scope_kinds[-1] in TYPE_SCOPES:
        return "method"
    return raw_kind


def _declaration(node, language: str, scope_kinds: list[str]):
    node_type = _kind(node)
    kind = DECLARATIONS.get(language, {}).get(node_type)
    name_node = _name_node(node)
    if node_type == "variable_declarator":
        value = _field(node, "value")
        if value is not None and _kind(value) in {"arrow_function", "function_expression", "function"}:
            kind = "function"
            name_node = _field(node, "name")
    if node_type == "impl_item" and name_node is None:
        name_node = _field(node, "type")
    if kind is None or name_node is None:
        return None
    name = _text(name_node, b"").strip()
    if not name or name in {"_", "anonymous"}:
        return None
    kind = _normal_kind(language, kind, scope_kinds)
    return kind, name


def _callee(node, language: str, source: bytes):
    target = _field(node, "function", "callee", "name", "method")
    receiver_node = _field(node, "object", "receiver", "operand", "target")
    if target is None:
        candidates = [c for c in _children(node) if _kind(c) in NAME_TYPES | ATTRIBUTE_TYPES]
        if not candidates:
            return "", ""
        target = candidates[-1]
    target_type = _kind(target)
    if target_type in ATTRIBUTE_TYPES:
        leaf = _field(target, "attribute", "property", "name", "field", "member")
        receiver = _field(target, "object", "operand", "scope", "value")
        if leaf is None:
            named = _children(target)
            leaf = named[-1] if named else None
            receiver = named[0] if len(named) > 1 else receiver
        return (_text(leaf, source).strip() if leaf else "",
                _text(receiver, source).strip() if receiver else "")
    if target_type in NAME_TYPES:
        return _text(target, source).strip(), (_text(receiver_node, source).strip() if receiver_node else "")
    named = _children(target)
    identifiers = [x for x in named if _kind(x) in NAME_TYPES]
    if identifiers:
        return _text(identifiers[-1], source).strip(), (_text(receiver_node, source).strip() if receiver_node else "")
    return "", ""

def _split_items(value: str) -> list[str]:
    # Import lists are syntax-bounded; this small splitter handles braces/parentheses.
    value = value.strip().strip("(){}").strip()
    out, current, depth, quote = [], [], 0, ""
    for char in value:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
        elif char in {"'", '"'}:
            quote = char
            current.append(char)
        elif char in "([{":
            depth += 1
            current.append(char)
        elif char in ")]}":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            if "".join(current).strip():
                out.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if "".join(current).strip():
        out.append("".join(current).strip())
    return out


def _imports_for_node(path: str, language: str, node, source: bytes) -> list[ImportRecord]:
    raw = _text(node, source).strip()
    line = _start_row(node) + 1
    out = []
    def add(module, imported, local, kind):
        if module:
            out.append(ImportRecord(path, module.strip(), imported.strip(), local.strip(), kind, line))
    if language == "python":
        m = re.match(r"from\s+([.\w]*)\s+import\s+(.+)", raw, re.S)
        if m:
            module = m.group(1)
            for item in _split_items(m.group(2)):
                parts = re.split(r"\s+as\s+", item.strip())
                imported = parts[0].strip()
                if imported.startswith("("):
                    imported = imported[1:].strip()
                if imported:
                    add(module, imported, parts[1].strip() if len(parts) > 1 else imported, "named")
            return out
        m = re.match(r"import\s+(.+)", raw, re.S)
        if m:
            for item in _split_items(m.group(1)):
                parts = re.split(r"\s+as\s+", item.strip())
                module = parts[0].strip()
                add(module, "*", parts[1].strip() if len(parts) > 1 else module.split(".")[0], "module")
        return out
    if language in {"typescript", "javascript"}:
        m = re.search(r"\bfrom\s*['\"]([^'\"]+)['\"]", raw, re.S)
        if not m:
            m = re.match(r"import\s*['\"]([^'\"]+)['\"]", raw, re.S)
            if m:
                add(m.group(1), "*", "", "side_effect")
            return out
        module = m.group(1)
        clause = raw[:m.start()].strip()
        clause = re.sub(r"^import\s+(?:type\s+)?", "", clause).strip().rstrip(",")
        if clause.startswith("{"):
            inside = clause.strip("{} ").strip()
            for item in _split_items(inside):
                parts = re.split(r"\s+as\s+", item.strip())
                name = parts[0].strip()
                add(module, name, parts[1].strip() if len(parts) > 1 else name, "named")
        elif clause.startswith("*"):
            alias = re.search(r"\bas\s+([A-Za-z_$][\w$]*)", clause)
            add(module, "*", alias.group(1) if alias else "", "namespace")
        elif clause:
            default = clause.split(",", 1)[0].strip()
            if default:
                add(module, "default", default, "default")
            named = re.search(r"\{([^}]*)\}", clause)
            if named:
                for item in _split_items(named.group(1)):
                    parts = re.split(r"\s+as\s+", item.strip())
                    name = parts[0].strip()
                    add(module, name, parts[1].strip() if len(parts) > 1 else name, "named")
        return out
    if language == "java":
        m = re.search(r"\bimport\s+(?:static\s+)?([\w.]+)\s*;", raw)
        if m:
            full = m.group(1)
            add(full, full.rsplit(".", 1)[-1], full.rsplit(".", 1)[-1], "qualified")
        return out
    if language == "kotlin":
        m = re.search(r"\bimport\s+([\w.]+)(?:\s+as\s+(\w+))?", raw)
        if m:
            full = m.group(1)
            add(full, full.rsplit(".", 1)[-1], m.group(2) or full.rsplit(".", 1)[-1], "qualified")
        return out
    if language == "go":
        m = re.search(r'(?:(\w+)\s+)?["\']([^"\']+)["\']', raw)
        if m:
            module = m.group(2)
            add(module, "*", m.group(1) or module.rstrip("/").rsplit("/", 1)[-1], "module")
        return out
    if language == "rust":
        m = re.search(r"\buse\s+(.+?)\s*;", raw, re.S)
        if m:
            spec = m.group(1).strip()
            parts = re.split(r"\s+as\s+", spec)
            path_part = parts[0].strip()
            segments = path_part.split("::")
            imported = segments[-1].strip("{}")
            module = "::".join(segments[:-1])
            add(module, imported, parts[1].strip() if len(parts) > 1 else imported, "named")
        return out
    if language == "dart":
        m = re.search(r"\bimport\s+['\"]([^'\"]+)['\"](?:\s+as\s+(\w+))?", raw)
        if m:
            add(m.group(1), "*", m.group(2) or "", "module")
        return out
    return out


def parse_tree_sitter(path: str, language: str, text: str) -> ParseBundle | None:
    parser_name = _parser_name(language)
    if not parser_name or not parser_available(language):
        return None
    try:
        from tree_sitter_language_pack import get_parser
        registry = parser_registry()
        if registry is None or not registry.has_language(parser_name):
            return None
        parser = get_parser(parser_name)
        source = text.encode("utf-8")
        tree = parser.parse(source)
        if tree is None:
            return None
    except Exception:
        return None

    symbols: list[SymbolRecord] = []
    imports: list[ImportRecord] = []
    references: list[ReferenceRecord] = []
    metadata: list[SymbolAnalysisRecord] = []
    error_count = 0
    declaration_nodes = DECLARATIONS.get(language, {})
    call_types = CALL_TYPES.get(language, set())
    import_types = IMPORT_TYPES.get(language, set())

    def visit(node, scopes: list[tuple[str, str]], owner_id: str, type_scope: str):
        nonlocal error_count
        if node.is_error or node.is_missing:
            error_count += 1
        scope_names = [x[0] for x in scopes]
        scope_kinds = [x[1] for x in scopes]
        declaration = _declaration(node, language, scope_kinds)
        next_scopes = scopes
        next_owner = owner_id
        next_type_scope = type_scope
        if declaration:
            kind, name = declaration
            start = _start_row(node) + 1
            end = max(start, _end_row(node) + 1)
            qname = ".".join(scope_names + [name])
            body = _body_node(node)
            if _kind(node) == "variable_declarator":
                value = _field(node, "value")
                body = _body_node(value) if value is not None else body
            signature = _signature(node, body, source)
            symbol_id = f"{path}:{qname}:{start}"
            symbols.append(SymbolRecord(symbol_id, name, qname, kind, path, language, start, end, signature))
            declaration_bytes = source[_start_byte(node):_end_byte(node)]
            body_bytes = source[_start_byte(body):_end_byte(body)] if body is not None else declaration_bytes
            signature_bytes = signature.encode("utf-8")
            metadata.append(SymbolAnalysisRecord(
                symbol_id, type_scope, _hash(signature_bytes), _hash(body_bytes), _hash(declaration_bytes)))
            next_scopes = scopes + [(name, kind)]
            if kind in CALLABLES:
                next_owner = symbol_id
            if kind in TYPE_SCOPES:
                next_type_scope = qname
        if _kind(node) in import_types:
            imports.extend(_imports_for_node(path, language, node, source))
        if _kind(node) in call_types and owner_id:
            target, receiver = _callee(node, language, source)
            if target and target not in {"if", "for", "while", "switch", "catch", "return"}:
                references.append(ReferenceRecord(
                    owner_id, target, receiver, _kind(node), path,
                    _start_row(node) + 1, _start_byte(node), _end_byte(node)))
        for child in _children(node):
            visit(child, next_scopes, next_owner, next_type_scope)

    visit(tree.root_node, [], "", "")
    status = "partial" if error_count else "ok"
    return ParseBundle(
        symbols, imports, references,
        FileAnalysisRecord(path, "tree_sitter", status, error_count,
                           _version("tree-sitter-language-pack")),
        metadata,
    )


def _module_candidates(module: str, extensions: tuple[str, ...]) -> list[str]:
    module = module.replace(".", "/").strip("/")
    if not module:
        return []
    if PurePosixPath(module).suffix:
        return [module]
    return [module + ext for ext in extensions] + [module + "/__init__" + ext for ext in extensions]


def _resolve_import(root: Path, record: ImportRecord, known_files: set[str]) -> str:
    importer = record.file_path
    lang = Path(importer).suffix.lower()
    module = record.module_specifier
    candidates: list[str] = []
    if record.import_kind in {"named", "module"} and lang in {".py", ".pyi"}:
        if module.startswith("."):
            level = len(module) - len(module.lstrip("."))
            suffix = module[level:]
            package = list(PurePosixPath(importer).parent.parts)
            if PurePosixPath(importer).name == "__init__.py":
                package = list(PurePosixPath(importer).parent.parts)
            base = package[:max(0, len(package) - level + 1)]
            parts = base + ([x for x in suffix.split(".") if x] if suffix else [])
            stem = "/".join(parts)
        else:
            stem = module.replace(".", "/")
        candidates.extend(_module_candidates(stem, (".py", ".pyi")))
        if record.import_kind == "named" and not stem:
            pass
    elif module.startswith(".") and lang in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        stem = posixpath.normpath(posixpath.join(posixpath.dirname(importer), module))
        candidates.extend(_module_candidates(stem, (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".d.ts")))
        candidates.extend(stem + "/index" + ext for ext in (".ts", ".tsx", ".js", ".jsx"))
    elif lang in {".java", ".kt", ".kts"}:
        stem = module.replace(".", "/")
        candidates.extend(_module_candidates(stem, (".java", ".kt", ".kts")))
    elif lang == ".dart":
        if module.startswith("package:"):
            candidates.append("lib/" + module[len("package:"):])
        elif module.startswith("."):
            candidates.append(posixpath.normpath(posixpath.join(posixpath.dirname(importer), module)))
    elif lang == ".rs":
        stem = module.replace("crate::", "src/").replace("self::", posixpath.dirname(importer) + "/").replace("super::", "../")
        stem = stem.replace("::", "/")
        candidates.extend(_module_candidates(stem, (".rs",)))
        candidates.extend([stem + "/mod.rs", stem + "/lib.rs"])
    for candidate in candidates:
        normalized = posixpath.normpath(candidate)
        if normalized in known_files:
            return normalized
    return ""


def resolve_references(root: str | Path, symbols: list[SymbolRecord],
                       imports: list[ImportRecord], references: list[ReferenceRecord],
                       symbol_analysis: list[SymbolAnalysisRecord]) -> list[ImportRecord]:
    """Resolve only unique same-file, same-class and explicit-import bindings."""
    root_path = Path(root)
    known_files = {s.file_path for s in symbols}
    by_file: dict[str, dict[str, list[SymbolRecord]]] = {}
    by_id = {s.symbol_id: s for s in symbols}
    for symbol in symbols:
        by_file.setdefault(symbol.file_path, {}).setdefault(symbol.name, []).append(symbol)
    meta_by_id = {m.symbol_id: m for m in symbol_analysis}
    aliases: dict[str, dict[str, ImportRecord]] = {}
    for item in imports:
        item.resolved_path = _resolve_import(root_path, item, known_files)
        if item.local_name:
            aliases.setdefault(item.file_path, {})[item.local_name] = item
    for ref in references:
        source_symbol = by_id.get(ref.source_id)
        if source_symbol is None:
            continue
        file_aliases = aliases.get(ref.evidence_path, {})
        # Explicit imported function alias: from module import name as alias.
        if not ref.receiver and ref.target_name in file_aliases:
            imported = file_aliases[ref.target_name]
            if imported.resolved_path and imported.imported_name not in {"", "*"}:
                candidates = by_file.get(imported.resolved_path, {}).get(imported.imported_name, [])
                candidates = [x for x in candidates if x.kind in CALLABLES]
                if len(candidates) == 1:
                    ref.target_id = candidates[0].symbol_id
                    ref.resolution = "tree_sitter_import_binding"
                    ref.confidence = 0.90
                    ref.reason = "Explicit import maps to one local declaration; no type-checker proof."
                    continue
        # Namespace import: moduleAlias.function().
        if ref.receiver and ref.receiver in file_aliases:
            imported = file_aliases[ref.receiver]
            if imported.resolved_path and imported.imported_name == "*":
                candidates = by_file.get(imported.resolved_path, {}).get(ref.target_name, [])
                candidates = [x for x in candidates if x.kind in CALLABLES]
                if len(candidates) == 1:
                    ref.target_id = candidates[0].symbol_id
                    ref.resolution = "tree_sitter_import_binding"
                    ref.confidence = 0.90
                    ref.reason = "Namespace import maps to one local declaration; no type-checker proof."
                    continue
        # self.foo / this.foo / cls.foo inside the nearest class-like scope.
        if ref.receiver.split(".")[-1] in {"self", "this", "cls"}:
            source_meta = meta_by_id.get(ref.source_id)
            scope = source_meta.scope_name if source_meta else ""
            if scope:
                qname = scope + "." + ref.target_name
                candidates = [s for s in symbols if s.file_path == ref.evidence_path
                              and s.qualified_name == qname and s.kind in CALLABLES]
                if len(candidates) == 1:
                    ref.target_id = candidates[0].symbol_id
                    ref.resolution = "tree_sitter_same_class"
                    ref.confidence = 0.85
                    ref.reason = "Receiver is self/this/cls and one method exists in the enclosing class."
                    continue
        # Unique same-file declaration only. Ambiguous or dynamic targets stay unresolved.
        if not ref.receiver:
            candidates = [x for x in by_file.get(ref.evidence_path, {}).get(ref.target_name, [])
                          if x.kind in CALLABLES and x.symbol_id != ref.source_id]
            if len(candidates) == 1:
                ref.target_id = candidates[0].symbol_id
                ref.resolution = "tree_sitter_same_file_unique"
                ref.confidence = 0.80
                ref.reason = "One same-file declaration matches the syntax name; shadowing is not type-checked."
            elif len(candidates) > 1:
                ref.reason = "Multiple same-file declarations share this name."
            elif ref.target_name in file_aliases:
                ref.reason = "Import exists but its target file or symbol could not be resolved."
            else:
                ref.reason = "No unique local declaration or supported explicit import binding."
        else:
            ref.reason = "Receiver type is not known; member dispatch remains unresolved."
    return imports
