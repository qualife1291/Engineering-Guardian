"""Read-only service boundary shared by the CLI, Claude Code MCP and tests."""
from __future__ import annotations
import time
from pathlib import Path
from .store import UCGStore
from .engine import scan_workspace
from .context import build_context_pack, StaleSnapshotError
from .diagnostics import Diagnostics, index_path, support_bundle
from .scanner import scan_files
from .treesitter import install_parsers as install_tree_sitter_parsers, parser_status as tree_sitter_status


class GuardianService:
    def __init__(self, root: str, db: str | None = None, diagnostics: bool = True):
        self.root=Path(root).expanduser().resolve(strict=True)
        if not self.root.is_dir():
            raise NotADirectoryError("Workspace root must be a directory")
        self.db=Path(db).expanduser().resolve() if db else index_path(self.root)
        self.metrics=Diagnostics(self.root, enabled=diagnostics)

    def _snapshot(self, store: UCGStore) -> str:
        snapshot=store.latest_snapshot(str(self.root))
        if not snapshot:
            raise RuntimeError("INDEX_MISSING: run guardian_scan first")
        return snapshot

    def _check_freshness(self, store: UCGStore, snapshot: str) -> dict:
        actual,skipped=scan_files(self.root)
        expected=store.get_file_fingerprints(snapshot)
        current={f.path:f.fingerprint for f in actual}
        changed=sum(1 for p,v in current.items() if expected.get(p)!=v)
        deleted=len(set(expected)-set(current))
        return {"status":"fresh" if expected==current else "stale",
                "changed_or_added_files":changed,"deleted_files":deleted,"skipped_files":len(skipped)}

    def scan(self) -> dict:
        try:
            result=scan_workspace(str(self.root),str(self.db))
            self.metrics.record_scan(result)
            return {"snapshot_id":result["snapshot_id"],"overview":result["overview"],
                    "cache_hit":result["cache_hit"],"parsed_files":result["parsed_files"],
                    "reused_files":result["reused_files"],"skipped_files":result["skipped_files"],
                    "warnings":len(result["diagnostics"]),"timings_seconds":result["timings_seconds"],
                    "relationships":"Tree-sitter syntactic bindings where available; fallback AST candidates are heuristic.",
                    "parser_coverage":result.get("coverage",{})}
        except Exception as exc:
            self.metrics.error("scan",exc)
            raise

    def status(self) -> dict:
        begin=time.perf_counter()
        store=UCGStore(self.db)
        try:
            snapshot=store.latest_snapshot(str(self.root))
            if snapshot is None:
                result={"index_status":"missing","snapshot_id":None}
            else:
                current=self._check_freshness(store,snapshot)
                result={"snapshot_id":snapshot,"index_status":current["status"],**current,
                        "overview":store.overview(snapshot),"parser_coverage":store.parser_coverage(snapshot)}
        finally: store.close()
        self.metrics.log("index_status",index_status=result["index_status"],success=True,
                         duration_ms=round(1000*(time.perf_counter()-begin),3))
        return result

    def _guard_latest(self, store: UCGStore) -> str:
        snapshot=self._snapshot(store)
        fresh=self._check_freshness(store,snapshot)
        if fresh["status"]!="fresh":
            raise StaleSnapshotError("INDEX_STALE: source changed since last scan; run guardian_scan again")
        return snapshot

    def overview(self) -> dict:
        start=time.perf_counter(); store=UCGStore(self.db)
        try:
            snapshot=self._guard_latest(store)
            result={"snapshot_id":snapshot,**store.overview(snapshot),
                    "relationships":"Tree-sitter syntactic bindings where available; fallback AST candidates are heuristic.",
                    "parser_coverage":store.parser_coverage(snapshot)}
        finally:store.close()
        self.metrics.log("tool_call",tool_name="guardian_overview",success=True,duration_ms=round(1000*(time.perf_counter()-start),3))
        return result

    def find_symbol(self, query: str, limit: int = 20) -> dict:
        start=time.perf_counter(); store=UCGStore(self.db)
        try:
            snapshot=self._guard_latest(store)
            hits=store.search(snapshot,query,max(1,min(limit,40)))
        finally:store.close()
        self.metrics.log("tool_call",tool_name="guardian_find_symbol",success=True,
                         duration_ms=round(1000*(time.perf_counter()-start),3))
        return {"snapshot_id":snapshot,"query":query,"symbols":hits}

    def relations(self, symbol_id: str, direction: str, max_depth: int = 2) -> dict:
        start=time.perf_counter(); store=UCGStore(self.db)
        try:
            snapshot=self._guard_latest(store)
            symbol=store.conn.execute("SELECT 1 FROM symbols WHERE snapshot_id=? AND symbol_id=?",(snapshot,symbol_id)).fetchone()
            if not symbol:
                raise KeyError("Unknown symbol_id in current snapshot")
            edges=store.traverse(snapshot,symbol_id,direction,max(1,min(max_depth,4)),max_nodes=200)
            ids={edge["to"] for edge in edges}
            node_map={}
            for sid in ids:
                row=store.conn.execute("SELECT qualified_name,file_path,start_line FROM symbols WHERE snapshot_id=? AND symbol_id=?",(snapshot,sid)).fetchone()
                if row:node_map[sid]={"qualified_name":row[0],"file_path":row[1],"start_line":row[2]}
            for edge in edges:
                edge["symbol"]=node_map.get(edge["to"])
        finally:store.close()
        tool="guardian_get_callees" if direction=="forward" else "guardian_get_callers"
        self.metrics.log("tool_call",tool_name=tool,success=True,
                         duration_ms=round(1000*(time.perf_counter()-start),3))
        return {"snapshot_id":snapshot,"direction":direction,"edges":edges[:200],
                "relationships":"Tree-sitter syntactic bindings where available; fallback AST candidates are heuristic.",
                    "parser_coverage":store.parser_coverage(snapshot)}

    def context(self, query: str, max_chars: int = 12000) -> dict:
        started=time.perf_counter(); store=UCGStore(self.db)
        try:
            snapshot=self._guard_latest(store)
        finally:store.close()
        result=build_context_pack(str(self.db),snapshot,query,max(256,min(max_chars,32000)))
        self.metrics.log("context",success=True,context_characters=result["context_characters"],
                         context_tokens_estimate=result["estimated_tokens_char_div_4"],
                         truncated=result["truncated"],duration_ms=round(1000*(time.perf_counter()-started),3))
        return result


    # Offline service methods use the same freshness guard and diagnostic timer
    # as the original MCP/CLI tools. No LLM, source writes or shell execution.
    def _offline_query(self, tool_name: str, reader):
        started=time.perf_counter()
        try:
            store=UCGStore(self.db)
            try:
                snapshot=self._guard_latest(store)
                result=reader(store,snapshot)
            finally:
                store.close()
            self.metrics.log("tool_call",tool_name=tool_name,success=True,
                             duration_ms=round(1000*(time.perf_counter()-started),3))
            return result
        except Exception as exc:
            self.metrics.error("tool_call",exc,tool_name=tool_name)
            raise

    def tree(self, depth: int = 5, limit: int = 200) -> dict:
        from . import offline
        return self._offline_query("guardian_tree",lambda store,s:offline.tree(store,s,depth,limit))

    def outline(self, path: str, limit: int = 120) -> dict:
        from . import offline
        return self._offline_query("guardian_outline",lambda store,s:offline.outline(store,s,path,limit))

    def hotspots(self, min_lines: int = 300, min_function_lines: int = 80, limit: int = 30) -> dict:
        from . import offline
        return self._offline_query(
            "guardian_hotspots",
            lambda store,s:offline.hotspots(store,s,min_lines,min_function_lines,limit))

    def repo_map(self, focus: str = "", max_chars: int = 6000, limit: int = 80) -> dict:
        from . import offline
        return self._offline_query(
            "guardian_repo_map",
            lambda store,s:offline.repo_map(store,s,focus,max_chars,limit))

    def diff(self, base: str | None = None, head: str | None = None, limit: int = 100) -> dict:
        from . import offline
        return self._offline_query(
            "guardian_snapshot_diff",
            lambda store,s:offline.diff(store,str(self.root),base,head,limit))

    def brief(self, focus: str = "", max_chars: int = 6000) -> dict:
        from . import offline
        def create(store,snapshot):
            overview={"snapshot_id":snapshot,**store.overview(snapshot)}
            filetree=offline.tree(store,snapshot,3,300)
            hot=offline.hotspots(store,snapshot,300,80,10)
            mapping=offline.repo_map(store,snapshot,focus,max_chars,60)
            content=offline.brief(overview,filetree,hot,mapping)
            return {"snapshot_id":snapshot,"markdown":content,"characters":len(content),
                    "notice":"Offline preview, not written to the scanned workspace."}
        return self._offline_query("guardian_offline_brief",create)


    def parser_status(self) -> dict:
        result = tree_sitter_status()
        try:
            store = UCGStore(self.db)
            try:
                snapshot = store.latest_snapshot(str(self.root))
                result["indexed_snapshot"] = snapshot
                result["indexed_coverage"] = store.parser_coverage(snapshot) if snapshot else None
            finally:
                store.close()
        except Exception:
            result["indexed_snapshot"] = None
            result["indexed_coverage"] = None
        return result

    def install_parsers(self, languages: list[str]) -> dict:
        result = install_tree_sitter_parsers(languages)
        self.metrics.log("tool_call", tool_name="guardian_parser_install", success=True,
                         duration_ms=0.0)
        return result

    def change_impact(self, base: str | None = None, head: str | None = None,
                      depth: int = 3, limit: int = 100) -> dict:
        from . import offline
        return self._offline_query(
            "guardian_change_impact",
            lambda store,s:offline.change_impact(store,str(self.root),base,head,depth,limit))

    def support_log(self) -> dict:
        p=support_bundle(self.root)
        self.metrics.log("support_bundle",success=True)
        return {"bundle_path":str(p),"contains_source":False,
                "hint":"Share this ZIP for performance debugging; do not share the SQLite index"}
