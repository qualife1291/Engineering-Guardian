from dataclasses import dataclass


@dataclass(slots=True)
class FileRecord:
    path: str
    language: str
    size_bytes: int
    line_count: int
    fingerprint: str
    status: str = "unchanged"


@dataclass(slots=True)
class SymbolRecord:
    symbol_id: str
    name: str
    qualified_name: str
    kind: str
    file_path: str
    language: str
    start_line: int
    end_line: int
    signature: str = ""


@dataclass(slots=True)
class EdgeRecord:
    source_id: str
    target_id: str
    relation: str
    resolution: str
    evidence_path: str
    evidence_line: int


@dataclass(slots=True)
class FileAnalysisRecord:
    file_path: str
    parser_backend: str
    parse_status: str
    error_count: int
    parser_version: str


@dataclass(slots=True)
class ImportRecord:
    file_path: str
    module_specifier: str
    imported_name: str
    local_name: str
    import_kind: str
    line: int
    resolved_path: str = ""


@dataclass(slots=True)
class ReferenceRecord:
    source_id: str
    target_name: str
    receiver: str
    syntax_kind: str
    evidence_path: str
    evidence_line: int
    start_byte: int
    end_byte: int
    resolution: str = "unresolved"
    target_id: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass(slots=True)
class SymbolAnalysisRecord:
    symbol_id: str
    scope_name: str
    signature_hash: str
    body_hash: str
    declaration_hash: str
