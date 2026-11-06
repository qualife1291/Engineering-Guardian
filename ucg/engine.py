"""Incremental versioned code index with optional Tree-sitter syntax analysis."""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from . import __version__
from .models import EdgeRecord, FileAnalysisRecord, SymbolAnalysisRecord
from .parser import parse_file
from .scanner import fingerprint, scan_files
from .store import UCGStore
from .treesitter import parse_tree_sitter, parser_available, resolve_references

CALL_PATTERN = re.compile(r"\b([A-Za-z_]\w*)\s*\(")


class SourceChangedDuringScan(RuntimeError):
    """Source bytes changed between inventory and parsing; no snapshot was committed."""


def snapshot_identity(root: Path, records: list) -> str:
    h = hashlib.blake2b(digest_size=16)
    for value in (str(root), __version__, "graph-schema-v4"):
        h.update(value.encode("utf-8"))
        h.update(b"\0")
    for rec in records:
        for value in (rec.path, rec.language, rec.fingerprint):
            h.update(value.encode("utf-8"))
            h.update(b"\0")
    return "snap_" + h.hexdigest()


def call_sites_for_symbol(source, lines: list[str]) -> list[tuple[str, str, str, int]]:
    """Legacy fallback-only call candidates; never used for Tree-sitter files."""
    body = "\n".join(lines[max(0, source.start_line - 1):source.end_line])
    found = {}
    for match in CALL_PATTERN.finditer(body):
        name = match.group(1)
        if name not in found:
            found[name] = source.start_line + body[:match.start()].count("\n")
    return [(source.symbol_id, name, source.file_path, line) for name, line in found.items()]


def _fallback_backend(language: str) -> str:
    return "python_ast" if language == "python" else "regex_heuristic"


def _expected_backend(language: str) -> str:
    return "tree_sitter" if parser_available(language) else _fallback_backend(language)


def _fallback_symbol_analysis(symbols, text: str) -> list[SymbolAnalysisRecord]:
    lines = text.splitlines()
    out = []
    for symbol in symbols:
        body = "\n".join(lines[max(0, symbol.start_line - 1):symbol.end_line]).encode("utf-8")
        prefix = symbol.qualified_name.rsplit(".", 1)[0] if "." in symbol.qualified_name else ""
        digest = hashlib.blake2b(body, digest_size=16).hexdigest()
        signature_hash = hashlib.blake2b(symbol.signature.encode("utf-8"), digest_size=16).hexdigest()
        out.append(SymbolAnalysisRecord(symbol.symbol_id, prefix, signature_hash, digest, digest))
    return out


def scan_workspace(root: str, db_path: str, snapshot_id: str | None = None):
    started = time.perf_counter()
    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError("Workspace root must be a directory")
    records, skipped = scan_files(root_path)
    scan_done = time.perf_counter()
    computed_id = snapshot_identity(root_path, records)
    requested_id = snapshot_id
    if requested_id is not None:
        computed_id = requested_id
    store = UCGStore(db_path)
    try:
        if requested_id and store.has_snapshot(requested_id, str(root_path)):
            old = store.get_file_fingerprints(requested_id)
            if old != {item.path: item.fingerprint for item in records}:
                raise SourceChangedDuringScan("Explicit snapshot ID cannot be reused for different source content")
        if store.has_snapshot(computed_id, str(root_path)):
            overview = store.overview(computed_id)
            coverage = store.parser_coverage(computed_id)
            total = time.perf_counter() - started
            return {
                "snapshot_id": computed_id, "root": str(root_path), "overview": overview,
                "cache_hit": True, "parsed_files": 0, "reused_files": len(records),
                "skipped_files": len(skipped), "diagnostics": [],
                "timings_seconds": {"scan": scan_done - started, "parse_and_symbols": 0.0,
                                    "candidate_graph": 0.0, "persist": 0.0, "total": total},
                "coverage": {"inventory_files": len(records), "symbols_extracted": overview["symbols"],
                             "candidate_edges": overview["edges"], **coverage},
            }

        previous = store.latest_snapshot(str(root_path))
        old_hashes = store.get_file_fingerprints(previous) if previous else {}
        all_symbols = []
        call_sites = []
        imports = []
        references = []
        file_analysis = []
        symbol_analysis = []
        diagnostics = []
        parsed = 0
        reused = 0

        for record in records:
            expected_backend = _expected_backend(record.language)
            old_analysis = store.get_file_analysis_for_file(previous, record.path) if previous else None
            can_reuse = (
                previous
                and old_hashes.get(record.path) == record.fingerprint
                and old_analysis is not None
                and old_analysis.parser_backend == expected_backend
            )
            if can_reuse:
                all_symbols.extend(store.get_symbols_for_file(previous, record.path))
                call_sites.extend(store.get_call_sites_for_file(previous, record.path))
                imports.extend(store.get_imports_for_file(previous, record.path))
                references.extend(store.get_references_for_file(previous, record.path))
                file_analysis.append(old_analysis)
                symbol_analysis.extend(store.get_symbol_analysis_for_file(previous, record.path))
                reused += 1
                continue

            path = root_path / record.path
            if path.is_symlink() or not path.resolve().is_relative_to(root_path):
                raise SourceChangedDuringScan("Workspace file became a symlink during scan")
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise SourceChangedDuringScan("Source file became unreadable during scan") from exc
            if fingerprint(data) != record.fingerprint:
                raise SourceChangedDuringScan("Source file modified during scan; retry")
            text = data.decode("utf-8", errors="replace")
            bundle = parse_tree_sitter(record.path, record.language, text)
            if bundle is not None:
                all_symbols.extend(bundle.symbols)
                imports.extend(bundle.imports)
                references.extend(bundle.references)
                file_analysis.append(bundle.file_analysis)
                symbol_analysis.extend(bundle.symbol_analysis)
                call_sites.extend((x.source_id, x.target_name, x.evidence_path, x.evidence_line)
                                  for x in bundle.references)
                if bundle.file_analysis.error_count:
                    diagnostics.append({"type": "tree_sitter_parse_errors", "language": record.language,
                                        "count": bundle.file_analysis.error_count})
            else:
                symbols = parse_file(record.path, record.language, text)
                all_symbols.extend(symbols)
                lines = text.splitlines()
                for symbol in symbols:
                    if symbol.kind in {"function", "method"}:
                        call_sites.extend(call_sites_for_symbol(symbol, lines))
                backend = _fallback_backend(record.language)
                file_analysis.append(FileAnalysisRecord(
                    record.path, backend, "heuristic", 0, "stdlib"))
                symbol_analysis.extend(_fallback_symbol_analysis(symbols, text))
                if not symbols and record.line_count:
                    diagnostics.append({"type": "no_symbols_or_parse_failure", "language": record.language})
            parsed += 1

        parse_done = time.perf_counter()
        imports = resolve_references(root_path, all_symbols, imports, references, symbol_analysis)
        by_id = {s.symbol_id: s for s in all_symbols}
        edges = []
        for ref in references:
            if ref.target_id and ref.source_id in by_id and ref.target_id in by_id:
                edges.append(EdgeRecord(ref.source_id, ref.target_id, "CALLS",
                                        ref.resolution, ref.evidence_path, ref.evidence_line))

        # Preserve clearly-labelled regex candidates only for fallback files.
        fallback_paths = {x.file_path for x in file_analysis if x.parser_backend != "tree_sitter"}
        by_name = {}
        for symbol in all_symbols:
            if symbol.kind in {"function", "method"}:
                by_name.setdefault(symbol.name, []).append(symbol)
        for src, name, evidence_path, line in call_sites:
            if evidence_path not in fallback_paths:
                continue
            source = by_id.get(src)
            if source is None:
                continue
            targets = by_name.get(name, [])
            local = [s for s in targets if s.file_path == source.file_path and s.symbol_id != src]
            if local:
                chosen = local[:3]
            elif len(targets) == 1 and targets[0].symbol_id != src:
                chosen = targets
            else:
                continue
            edges.extend(EdgeRecord(src, target.symbol_id, "CALLS", "ast_candidate",
                                    evidence_path, line) for target in chosen)
        # De-duplicate graph edges produced by overlapping call syntax.
        unique_edges = {}
        for edge in edges:
            key = (edge.source_id, edge.target_id, edge.relation, edge.resolution,
                   edge.evidence_path, edge.evidence_line)
            unique_edges[key] = edge
        edges = list(unique_edges.values())
        graph_done = time.perf_counter()

        after, _ = scan_files(root_path)
        if [(f.path, f.fingerprint) for f in records] != [(f.path, f.fingerprint) for f in after]:
            raise SourceChangedDuringScan("Source changed during scan; no snapshot written")
        store.commit_snapshot(computed_id, str(root_path), records, all_symbols, call_sites, edges,
                              file_analysis, imports, references, symbol_analysis)
        overview = store.overview(computed_id)
        coverage = store.parser_coverage(computed_id)
        end = time.perf_counter()
        return {
            "snapshot_id": computed_id, "root": str(root_path), "overview": overview,
            "cache_hit": False, "parsed_files": parsed, "reused_files": reused,
            "skipped_files": len(skipped), "diagnostics": diagnostics,
            "timings_seconds": {"scan": scan_done - started, "parse_and_symbols": parse_done - scan_done,
                                "candidate_graph": graph_done - parse_done,
                                "persist": end - graph_done, "total": end - started},
            "coverage": {"inventory_files": len(records), "symbols_extracted": len(all_symbols),
                         "candidate_edges": len(edges), **coverage},
        }
    finally:
        store.close()
