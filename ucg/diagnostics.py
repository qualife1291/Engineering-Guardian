"""Privacy-aware operational telemetry for reproducible debugging and upgrades.

NO source content, prompts, absolute paths, tokens, credentials, file names or
call arguments are stored in diagnostics. Runtime fields are allowlisted.
"""
from __future__ import annotations
import hashlib
import json
import os
import platform
import statistics
import sys
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

LOG_FORMAT = 1
SAFE_EVENTS = {"scan", "tool_call", "context", "index_status", "self_check", "support_bundle"}
SAFE_FIELDS = {
    "duration_ms", "success", "cache_hit", "files", "lines", "symbols", "edges",
    "parsed_files", "reused_files", "skipped_files", "diagnostic_count",
    "context_characters", "context_tokens_estimate", "truncated", "index_status",
    "tool_name", "failure_type", "error_code", "scan_ms", "parse_ms", "graph_ms", "persist_ms",
}
SAFE_TOOLS = {"guardian_scan", "guardian_overview", "guardian_find_symbol", "guardian_get_callers",
              "guardian_get_callees", "guardian_get_context", "guardian_index_status", "guardian_support_log",
              "guardian_tree", "guardian_outline", "guardian_hotspots", "guardian_repo_map",
              "guardian_snapshot_diff", "guardian_offline_brief"}


def data_home() -> Path:
    value = os.environ.get("GUARDIAN_HOME")
    home = Path(value).expanduser() if value else Path.home() / ".engineering-guardian"
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        home.chmod(0o700)
    except OSError:
        pass
    return home.resolve()


def workspace_key(root: str | Path) -> str:
    """Nonreversible workspace fingerprint; never log raw paths."""
    return hashlib.sha256(str(Path(root).expanduser().resolve()).encode("utf-8")).hexdigest()[:16]


def index_path(root: str | Path) -> Path:
    folder=data_home()/"indexes"
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    return folder/f"{workspace_key(root)}.sqlite"


class Diagnostics:
    def __init__(self, workspace: str | Path, enabled: bool = True):
        self.enabled=enabled
        self.workspace_id=workspace_key(workspace)
        self.session_id=uuid.uuid4().hex[:16]
        self.started=time.perf_counter()
        now=datetime.now(timezone.utc)
        self.log_dir=data_home()/"diagnostics"/now.strftime("%Y-%m-%d")
        self.path=self.log_dir/f"{self.session_id}.jsonl"
        self.events=0
        self.errors=0
        if self.enabled:
            self.log_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
            self.log("self_check",success=True,error_code="session_started")

    def log(self,event:str,**fields) -> None:
        if not self.enabled: return
        if event not in SAFE_EVENTS:
            raise ValueError("unsupported log event")
        sanitized={k:v for k,v in fields.items()
                   if k in SAFE_FIELDS and isinstance(v,(int,float,str,bool)) and v is not None}
        if "tool_name" in sanitized and sanitized["tool_name"] not in SAFE_TOOLS:
            sanitized["tool_name"]="unknown"
        if "failure_type" in sanitized:
            sanitized["failure_type"] = str(sanitized["failure_type"])[:48].replace("/", "_")
        if "error_code" in sanitized:
            sanitized["error_code"] = str(sanitized["error_code"])[:48].replace("/", "_")
        record={"schema_version":LOG_FORMAT, "timestamp":datetime.now(timezone.utc).isoformat(),
                "session_id":self.session_id,"workspace_hash":self.workspace_id,"event":event,**sanitized}
        text=json.dumps(record,ensure_ascii=False,separators=(",",":"))
        try:
            with self.path.open("a",encoding="utf-8") as f:
                f.write(text+"\n")
            self.events+=1
            if record.get("success") is False:
                self.errors+=1
        except OSError:
            # Logging must never break the code navigation workflow.
            pass

    def record_scan(self,result:dict) -> None:
        t=result.get("timings_seconds",{})
        o=result.get("overview",{})
        self.log("scan",success=True,cache_hit=bool(result.get("cache_hit")),
                 files=int(o.get("files",0)),lines=int(o.get("lines",0)),
                 symbols=int(o.get("symbols",0)),edges=int(o.get("edges",0)),
                 parsed_files=int(result.get("parsed_files",0)),reused_files=int(result.get("reused_files",0)),
                 skipped_files=int(result.get("skipped_files",0)),
                 diagnostic_count=len(result.get("diagnostics",[])),
                 duration_ms=round(1000*t.get("total",0),3),scan_ms=round(1000*t.get("scan",0),3),
                 parse_ms=round(1000*t.get("parse_and_symbols",0),3),
                 graph_ms=round(1000*t.get("candidate_graph",0),3),
                 persist_ms=round(1000*t.get("persist",0),3))

    def error(self,event:str,exc:Exception,**fields) -> None:
        self.log(event,success=False,failure_type=type(exc).__name__,**fields)


def support_bundle(root: str | Path, output: str | Path | None=None) -> Path:
    """Export sanitized JSONL and an environment summary, never database/source."""
    folder=data_home()/"diagnostics"
    wid=workspace_key(root)
    now=datetime.now(timezone.utc)
    target=Path(output).expanduser().resolve() if output else data_home()/f"guardian-support-{now:%Y%m%d-%H%M%S}.zip"
    target.parent.mkdir(parents=True,exist_ok=True)
    selected=[]
    if folder.exists():
        for file in sorted(folder.glob("*/*.jsonl")):
            try:
                # Parse and re-sanitize to prevent externally edited log files
                rows=[json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]
                cleaned=[]
                for row in rows:
                    if row.get("workspace_hash") != wid or row.get("event") not in SAFE_EVENTS:
                        continue
                    fields={k:v for k,v in row.items() if k in SAFE_FIELDS and isinstance(v,(int,float,bool,str))}
                    cleaned.append({"schema_version":LOG_FORMAT,"event":row["event"],"workspace_hash":"redacted",
                                    "timestamp":str(row.get("timestamp", ""))[:40],**fields})
                if cleaned:
                    selected.append((f"logs/{file.parent.name}/{file.name}",cleaned))
            except (OSError,ValueError,TypeError,json.JSONDecodeError):
                continue
    metadata={"schema_version":LOG_FORMAT,"generated_at_utc":now.isoformat(),"workspace_hash":"redacted",
              "python_version":".".join(map(str,sys.version_info[:3])),
              "os":platform.system(),"architecture":platform.machine(),
              "log_files":len(selected),"privacy":"No source, prompts, file paths, tokens, or database files"}
    with zipfile.ZipFile(target,"w",zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("environment.json",json.dumps(metadata,ensure_ascii=False,indent=2))
        for name,rows in selected:
            zf.writestr(name,"\n".join(json.dumps(row,ensure_ascii=False) for row in rows)+"\n")
    return target


def diagnostic_summary(root: str | Path, max_sessions: int = 200) -> dict:
    """Aggregate only allowlisted metrics; do not expose source/path/prompt content."""
    log_root = data_home() / "diagnostics"
    key = workspace_key(root)
    event_counts: dict[str, int] = {}
    samples: dict[str, list[float]] = {"scan_ms": [], "tool_ms": [], "context_ms": []}
    failures = 0
    scans = 0
    cache_hits = 0
    parsed = 0
    reused = 0
    warnings = 0
    sessions = 0
    if log_root.is_dir():
        files = sorted(log_root.glob("*/*.jsonl"), reverse=True)
        for file in files[:max_sessions]:
            saw_matching = False
            try:
                with file.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        if len(line) > 100_000:  # Do not ingest arbitrary giant log lines.
                            continue
                        try:
                            record = json.loads(line)
                        except (json.JSONDecodeError, TypeError):
                            continue
                        if record.get("workspace_hash") != key or record.get("event") not in SAFE_EVENTS:
                            continue
                        saw_matching = True
                        event = record["event"]
                        event_counts[event] = event_counts.get(event, 0) + 1
                        if record.get("success") is False:
                            failures += 1
                        duration = record.get("duration_ms")
                        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and 0 <= duration < 1e8:
                            if event == "scan": samples["scan_ms"].append(float(duration))
                            elif event == "tool_call": samples["tool_ms"].append(float(duration))
                            elif event == "context": samples["context_ms"].append(float(duration))
                        if event == "scan" and record.get("success") is True:
                            scans += 1
                            cache_hits += int(record.get("cache_hit") is True)
                            parsed += int(record.get("parsed_files", 0)) if isinstance(record.get("parsed_files"), int) else 0
                            reused += int(record.get("reused_files", 0)) if isinstance(record.get("reused_files"), int) else 0
                            warnings += int(record.get("diagnostic_count", 0)) if isinstance(record.get("diagnostic_count"), int) else 0
            except OSError:
                continue
            sessions += int(saw_matching)

    def describe(values: list[float]) -> dict:
        if not values:
            return {"count": 0, "median_ms": None, "p95_ms": None}
        values.sort()
        index = max(0, int((len(values) - 1) * 0.95 + 0.999999))
        return {"count": len(values), "median_ms": round(statistics.median(values), 3),
                "p95_ms": round(values[index], 3)}

    return {"workspace_hash": key, "sessions": sessions, "events": event_counts,
            "failures": failures, "successful_scans": scans, "cache_hits": cache_hits,
            "scan_cache_hit_rate": round(cache_hits / scans, 4) if scans else None,
            "parsed_files_total": parsed, "reused_files_total": reused,
            "parser_warning_count": warnings, "timing": {k: describe(v) for k,v in samples.items()},
            "notice": "Operational metrics only: not code correctness, symbol recall or actual LLM latency"}
