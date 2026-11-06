from dataclasses import dataclass
from pathlib import Path

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
