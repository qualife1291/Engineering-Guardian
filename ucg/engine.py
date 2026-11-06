"""Incremental, versioned UCG scanner. All relationships are heuristic candidates."""
from __future__ import annotations
import hashlib
import re
import time
from pathlib import Path
from .scanner import scan_files, fingerprint
from .parser import parse_file
from .store import UCGStore
from .models import EdgeRecord
from . import __version__

CALL_PATTERN = re.compile(r"\b([A-Za-z_]\w*)\s*\(")

class SourceChangedDuringScan(RuntimeError):
    """Source bytes changed between inventory and parsing; no snapshot was committed."""


def snapshot_identity(root: Path, records: list) -> str:
    h = hashlib.blake2b(digest_size=16)
    for value in (str(root), __version__, "graph-schema-v3"):
        h.update(value.encode("utf-8")); h.update(b"\0")
    for rec in records:
        for value in (rec.path, rec.language, rec.fingerprint):
            h.update(value.encode("utf-8")); h.update(b"\0")
    return "snap_" + h.hexdigest()


def call_sites_for_symbol(source, lines: list[str]) -> list[tuple[str,str,str,int]]:
    """Return unresolved candidates; graph resolution happens after all files are known."""
    body = "\n".join(lines[max(0,source.start_line-1):source.end_line])
    found = {}
    for match in CALL_PATTERN.finditer(body):
        name = match.group(1)
        if name not in found:
            found[name] = source.start_line + body[:match.start()].count("\n")
    return [(source.symbol_id, name, source.file_path, line) for name,line in found.items()]


def scan_workspace(root: str, db_path: str, snapshot_id: str | None = None):
    started = time.perf_counter()
    root_path = Path(root).expanduser().resolve(strict=True)
    if not root_path.is_dir():
        raise NotADirectoryError("Workspace root must be a directory")
    records, skipped = scan_files(root_path)
    scan_done = time.perf_counter()
    computed_id = snapshot_identity(root_path, records)
    # Legacy explicit snapshot IDs exist for benchmark compatibility only.
    # They may never silently point to different source contents.
    requested_id = snapshot_id
    if requested_id is not None:
        computed_id = requested_id
    store=UCGStore(db_path)
    try:
        if requested_id and store.has_snapshot(requested_id, str(root_path)):
            old = store.get_file_fingerprints(requested_id)
            if old != {item.path: item.fingerprint for item in records}:
                raise SourceChangedDuringScan("Explicit snapshot ID cannot be reused for different source content")
        if store.has_snapshot(computed_id, str(root_path)):
            overview=store.overview(computed_id)
            total=time.perf_counter()-started
            return {"snapshot_id":computed_id,"root":str(root_path),"overview":overview,
                    "cache_hit":True,"parsed_files":0,"reused_files":len(records),
                    "skipped_files":len(skipped),"diagnostics":[],
                    "timings_seconds":{"scan":scan_done-started,"parse_and_symbols":0.,"candidate_graph":0.,"persist":0.,"total":total},
                    "coverage":{"inventory_files":len(records),"symbols_extracted":overview['symbols'],
                                "candidate_edges":overview['edges'],"edge_resolution":"ast_candidate; not compiler-verified"}}
        previous=store.latest_snapshot(str(root_path))
        old_hashes=store.get_file_fingerprints(previous) if previous else {}
        all_symbols=[]; call_sites=[]; diagnostics=[]
        parsed=0; reused=0
        for record in records:
            if previous and old_hashes.get(record.path) == record.fingerprint:
                all_symbols.extend(store.get_symbols_for_file(previous,record.path))
                call_sites.extend(store.get_call_sites_for_file(previous,record.path))
                reused+=1
                continue
            path=root_path/record.path
            if path.is_symlink() or not path.resolve().is_relative_to(root_path):
                raise SourceChangedDuringScan("Workspace file became a symlink during scan")
            try:
                data=path.read_bytes()
            except OSError as exc:
                raise SourceChangedDuringScan("Source file became unreadable during scan") from exc
            if fingerprint(data)!=record.fingerprint:
                raise SourceChangedDuringScan("Source file modified during scan; retry")
            text=data.decode("utf-8",errors="replace")
            symbols=parse_file(record.path,record.language,text)
            if not symbols and record.line_count:
                diagnostics.append({"type":"no_symbols_or_parse_failure","language":record.language})
            all_symbols.extend(symbols)
            lines=text.splitlines()
            for symbol in symbols:
                if symbol.kind in {"function","method"}:
                    call_sites.extend(call_sites_for_symbol(symbol,lines))
            parsed+=1
        parse_done=time.perf_counter()
        by_name={}
        for symbol in all_symbols:
            if symbol.kind in {"function","method"}:
                by_name.setdefault(symbol.name,[]).append(symbol)
        by_id={s.symbol_id:s for s in all_symbols}
        edges=[]
        for src,name,evidence_path,line in call_sites:
            source=by_id.get(src)
            if source is None: continue
            targets=by_name.get(name,[])
            local=[s for s in targets if s.file_path==source.file_path and s.symbol_id!=src]
            if local:
                chosen=local[:3]
            elif len(targets)==1 and targets[0].symbol_id!=src:
                chosen=targets
            else:
                continue
            edges.extend(EdgeRecord(src,target.symbol_id,"CALLS","ast_candidate",evidence_path,line) for target in chosen)
        graph_done=time.perf_counter()
        # Confirm the input snapshot did not change while processing.
        after, _ = scan_files(root_path)
        if [(f.path,f.fingerprint) for f in records] != [(f.path,f.fingerprint) for f in after]:
            raise SourceChangedDuringScan("Source changed during scan; no snapshot written")
        store.commit_snapshot(computed_id,str(root_path),records,all_symbols,call_sites,edges)
        overview=store.overview(computed_id)
        end=time.perf_counter()
        return {"snapshot_id":computed_id,"root":str(root_path),"overview":overview,
                "cache_hit":False,"parsed_files":parsed,"reused_files":reused,
                "skipped_files":len(skipped),"diagnostics":diagnostics,
                "timings_seconds":{"scan":scan_done-started,"parse_and_symbols":parse_done-scan_done,
                                   "candidate_graph":graph_done-parse_done,"persist":end-graph_done,"total":end-started},
                "coverage":{"inventory_files":len(records),"symbols_extracted":len(all_symbols),
                            "candidate_edges":len(edges),"edge_resolution":"ast_candidate; not compiler-verified"}}
    finally:
        store.close()
