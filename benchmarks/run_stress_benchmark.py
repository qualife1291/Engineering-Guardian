"""Measure cold, cached and one-file incremental indexing on generated corpora."""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import statistics
import sqlite3
import sys
import time
from pathlib import Path

from ucg.engine import scan_workspace
from ucg.store import UCGStore


def percentile(values, pct):
    if not values:
        return None
    values = sorted(values)
    return values[min(len(values)-1, max(0, round((pct/100)*(len(values)-1))))]


def summarize(values):
    return {"median":statistics.median(values) if values else None,
            "p95":percentile(values,95),"min":min(values) if values else None,
            "max":max(values) if values else None}


def peak_rss_mb():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value / (1024 * 1024) if sys.platform == "darwin" else value / 1024


def db_bytes(path: Path):
    return sum(p.stat().st_size for p in (path, Path(str(path)+"-wal"), Path(str(path)+"-shm")) if p.exists())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--db",default=".guardian-bench/index.sqlite")
    parser.add_argument("--output",default="stress-benchmark.json")
    parser.add_argument("--runs",type=int,default=3)
    parser.add_argument("--max-rss-mb",type=float,default=2048)
    parser.add_argument("--max-cold-seconds",type=float,default=600)
    args = parser.parse_args()
    if args.runs < 1 or args.runs > 10:
        raise SystemExit("runs must be between 1 and 10")
    root = Path(args.source).resolve(strict=True)
    base_db = Path(args.db).expanduser().resolve()
    base_db.parent.mkdir(parents=True,exist_ok=True)
    cold_seconds, cold_stage = [], []
    last_db = None
    last_result = None
    cpu_start = time.process_time()
    for index in range(args.runs):
        db = base_db.with_name(f"{base_db.stem}-{index}{base_db.suffix}")
        for suffix in ("","-wal","-shm"):
            Path(str(db)+suffix).unlink(missing_ok=True)
        started = time.perf_counter()
        result = scan_workspace(str(root),str(db))
        elapsed = time.perf_counter()-started
        cold_seconds.append(elapsed)
        cold_stage.append(result["timings_seconds"])
        last_db,last_result = db,result

    # An unchanged second invocation must take the content-addressed fast path.
    warm_started = time.perf_counter()
    warm = scan_workspace(str(root),str(last_db))
    warm_seconds = time.perf_counter()-warm_started

    # Change exactly one source file; unchanged files should be loaded in batched queries.
    candidates = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {
        ".py",".ts",".tsx",".js",".jsx",".java",".kt",".dart",".go",".rs",".sql",".proto"
    })
    incremental = None
    incremental_seconds = None
    if candidates:
        changed = candidates[0]
        suffix = changed.suffix.lower()
        comment = "#" if suffix in {".py",".pyi"} else "--" if suffix == ".sql" else "//"
        with changed.open("a",encoding="utf-8") as stream:
            stream.write(f"\n{comment} deterministic incremental benchmark marker\n")
        started = time.perf_counter()
        incremental = scan_workspace(str(root),str(last_db))
        incremental_seconds = time.perf_counter()-started

    store = UCGStore(last_db)
    try:
        query = "normalize_00000"
        search_times = []
        for _ in range(100):
            started = time.perf_counter()
            store.search(incremental["snapshot_id"] if incremental else last_result["snapshot_id"],query,20)
            search_times.append((time.perf_counter()-started)*1000)
        overview = store.overview(incremental["snapshot_id"] if incremental else last_result["snapshot_id"])
        coverage = store.parser_coverage(incremental["snapshot_id"] if incremental else last_result["snapshot_id"])
        graph_times = []
        hits = store.search(incremental["snapshot_id"] if incremental else last_result["snapshot_id"],query,1)
        if hits:
            for _ in range(100):
                started = time.perf_counter()
                store.traverse(incremental["snapshot_id"] if incremental else last_result["snapshot_id"],
                               hits[0]["symbol_id"],"forward",max_depth=4,max_nodes=1000,max_edges=5000)
                graph_times.append((time.perf_counter()-started)*1000)
    finally:
        store.close()

    cpu_seconds = time.process_time()-cpu_start
    if overview["symbols"] <= 0:
        raise SystemExit("Stress benchmark extracted zero symbols; parser coverage must not be accepted as a pass")
    if coverage.get("tree_sitter_files", 0) != files:
        raise SystemExit(
            f"Tree-sitter parsed {coverage.get('tree_sitter_files', 0)} of {files} files; "
            "polyglot grammar coverage is incomplete"
        )
    resolved_reference_count = sum(coverage.get("resolved_references", {}).values())
    if resolved_reference_count <= 0:
        raise SystemExit("No syntactic references resolved; the dependency graph may be blind")
    source_bytes = overview["bytes"]
    files = overview["files"]
    lines = overview["lines"]
    report = {
        "benchmark":"Engineering Guardian polyglot stress benchmark",
        "environment":{"python":platform.python_version(),"platform":platform.platform(),
                       "machine":platform.machine(),"cpu_count":os.cpu_count(),
                       "sqlite":sqlite3.sqlite_version},
        "dataset":{"name":root.name,"files":files,"lines":lines,"source_bytes":source_bytes,
                   "source_mb":round(source_bytes/(1024*1024),3),"languages":overview["languages"]},
        "cold_scan":{"wall_seconds":summarize(cold_seconds),"stage_seconds":{
            key:summarize([x[key] for x in cold_stage]) for key in cold_stage[0]},
            "files_per_second":round(files/statistics.median(cold_seconds),2),
            "lines_per_second":round(lines/statistics.median(cold_seconds),2),
            "mb_per_second":round(source_bytes/(1024*1024)/statistics.median(cold_seconds),2)},
        "warm_exact_cache":{"wall_seconds":warm_seconds,"cache_hit":warm["cache_hit"],
                            "parsed_files":warm["parsed_files"],"reused_files":warm["reused_files"]},
        "incremental_one_file":{"wall_seconds":incremental_seconds,
                                "parsed_files":incremental.get("parsed_files") if incremental else None,
                                "reused_files":incremental.get("reused_files") if incremental else None,
                                "changed_file":candidates[0].relative_to(root).as_posix() if candidates else None},
        "queries":{"symbol_search_ms":summarize(search_times),
                   "bounded_graph_walk_ms":summarize(graph_times)},
        "storage":{"sqlite_bytes_including_wal":db_bytes(last_db),
                   "sqlite_mb":round(db_bytes(last_db)/(1024*1024),3)},
        "resources":{"process_peak_rss_mb":round(peak_rss_mb(),2),"process_cpu_seconds":round(cpu_seconds,3)},
        "analysis_coverage":coverage,
        "scan_result":{"symbols":overview["symbols"],"edges":overview["edges"],
                       "skipped_files":last_result["skipped_files"],
                       "diagnostics":last_result["diagnostics"][:50],
                       "diagnostic_count":len(last_result["diagnostics"])},
        "interpretation":{"cold_scan_is_end_to_end":"includes inventory hashing, parsing, graph construction, consistency re-scan and SQLite commit",
                          "warm_scan":"still hashes the workspace to prove the snapshot is unchanged",
                          "incremental":"still inventories the workspace but should parse only the changed file",
                          "memory":"process high-water mark; includes interpreter and all benchmark runs",
                          "limitations":"synthetic corpus is reproducible but not a substitute for real customer repositories; static dependency coverage is not compiler/runtime truth"},
    }
    out=Path(args.output).expanduser()
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    if peak_rss_mb()>args.max_rss_mb:
        raise SystemExit(f"Peak RSS {peak_rss_mb():.1f} MB exceeded limit {args.max_rss_mb:.1f} MB")
    if statistics.median(cold_seconds)>args.max_cold_seconds:
        raise SystemExit(f"Median cold scan {statistics.median(cold_seconds):.1f}s exceeded limit {args.max_cold_seconds:.1f}s")
    if incremental and incremental["parsed_files"] != 1:
        raise SystemExit(f"Incremental scan parsed {incremental['parsed_files']} files; expected exactly one")
    if not warm["cache_hit"]:
        raise SystemExit("Unchanged warm scan did not hit the exact snapshot cache")


if __name__ == "__main__":
    main()
