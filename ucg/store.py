"""SQLite persistence for versioned, immutable source-code snapshots.

SQLite lives outside the target project by default. All writes to a new
snapshot are committed as a single transaction, making partial scans invisible.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from .models import (FileRecord, SymbolRecord, EdgeRecord, FileAnalysisRecord, ImportRecord, ReferenceRecord, SymbolAnalysisRecord)

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS snapshots(
  snapshot_id TEXT PRIMARY KEY, root_path TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snapshots_root ON snapshots(root_path,created_at);
CREATE TABLE IF NOT EXISTS files(
  snapshot_id TEXT NOT NULL, path TEXT NOT NULL, language TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, line_count INTEGER NOT NULL, fingerprint TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,path), FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id)
);
CREATE TABLE IF NOT EXISTS symbols(
  snapshot_id TEXT NOT NULL, symbol_id TEXT NOT NULL, name TEXT NOT NULL,
  qualified_name TEXT NOT NULL, kind TEXT NOT NULL, file_path TEXT NOT NULL,
  language TEXT NOT NULL, start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
  signature TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,symbol_id), FOREIGN KEY(snapshot_id,file_path) REFERENCES files(snapshot_id,path)
);
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(snapshot_id,name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified_name ON symbols(snapshot_id,qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(snapshot_id,file_path);
CREATE TABLE IF NOT EXISTS call_sites(
  snapshot_id TEXT NOT NULL, source_id TEXT NOT NULL,
  target_name TEXT NOT NULL, evidence_path TEXT NOT NULL,
  evidence_line INTEGER NOT NULL,
  PRIMARY KEY(snapshot_id,source_id,target_name,evidence_path,evidence_line)
);
CREATE INDEX IF NOT EXISTS idx_call_sites_file ON call_sites(snapshot_id,evidence_path);
CREATE TABLE IF NOT EXISTS edges(
  snapshot_id TEXT NOT NULL, source_id TEXT NOT NULL, target_id TEXT NOT NULL,
  relation TEXT NOT NULL, resolution TEXT NOT NULL, evidence_path TEXT NOT NULL,
  evidence_line INTEGER NOT NULL,
  PRIMARY KEY(snapshot_id,source_id,target_id,relation,evidence_path,evidence_line)
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(snapshot_id,source_id,relation);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(snapshot_id,target_id,relation);
CREATE TABLE IF NOT EXISTS file_analysis(
  snapshot_id TEXT NOT NULL, path TEXT NOT NULL, parser_backend TEXT NOT NULL,
  parse_status TEXT NOT NULL, error_count INTEGER NOT NULL, parser_version TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,path)
);
CREATE INDEX IF NOT EXISTS idx_file_analysis_backend ON file_analysis(snapshot_id,parser_backend);
CREATE TABLE IF NOT EXISTS imports(
  snapshot_id TEXT NOT NULL, file_path TEXT NOT NULL, module_specifier TEXT NOT NULL,
  imported_name TEXT NOT NULL, local_name TEXT NOT NULL, import_kind TEXT NOT NULL,
  line INTEGER NOT NULL, resolved_path TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(snapshot_id,file_path,module_specifier,imported_name,local_name,line)
);
CREATE INDEX IF NOT EXISTS idx_imports_resolved ON imports(snapshot_id,resolved_path,file_path);
CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(snapshot_id,file_path);
CREATE TABLE IF NOT EXISTS symbol_references(
  snapshot_id TEXT NOT NULL, source_id TEXT NOT NULL, target_name TEXT NOT NULL,
  receiver TEXT NOT NULL, syntax_kind TEXT NOT NULL, evidence_path TEXT NOT NULL,
  evidence_line INTEGER NOT NULL, start_byte INTEGER NOT NULL, end_byte INTEGER NOT NULL,
  resolution TEXT NOT NULL, target_id TEXT NOT NULL, confidence REAL NOT NULL,
  reason TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,source_id,evidence_path,start_byte,end_byte)
);
CREATE INDEX IF NOT EXISTS idx_references_target ON symbol_references(snapshot_id,target_id);
CREATE INDEX IF NOT EXISTS idx_references_source ON symbol_references(snapshot_id,source_id);
CREATE INDEX IF NOT EXISTS idx_references_file ON symbol_references(snapshot_id,evidence_path);
CREATE INDEX IF NOT EXISTS idx_references_name ON symbol_references(snapshot_id,target_name,target_id);
CREATE TABLE IF NOT EXISTS symbol_analysis(
  snapshot_id TEXT NOT NULL, symbol_id TEXT NOT NULL, scope_name TEXT NOT NULL,
  signature_hash TEXT NOT NULL, body_hash TEXT NOT NULL, declaration_hash TEXT NOT NULL,
  PRIMARY KEY(snapshot_id,symbol_id)
);
CREATE INDEX IF NOT EXISTS idx_symbol_analysis_scope ON symbol_analysis(snapshot_id,scope_name);
CREATE VIRTUAL TABLE IF NOT EXISTS symbol_fts USING fts5(snapshot_id UNINDEXED,symbol_id UNINDEXED,name,qualified_name,signature,file_path);
"""

class UCGStore:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, timeout=30)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def has_snapshot(self, snapshot_id: str, root: str | None = None) -> bool:
        if root is None:
            row = self.conn.execute("SELECT 1 FROM snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        else:
            row = self.conn.execute("SELECT 1 FROM snapshots WHERE snapshot_id=? AND root_path=?", (snapshot_id, root)).fetchone()
        return row is not None

    def latest_snapshot(self, root: str) -> str | None:
        row = self.conn.execute("SELECT snapshot_id FROM snapshots WHERE root_path=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (root,)).fetchone()
        return row[0] if row else None

    def get_file_fingerprints(self, snapshot_id: str) -> dict[str, str]:
        return dict(self.conn.execute("SELECT path,fingerprint FROM files WHERE snapshot_id=?", (snapshot_id,)).fetchall())

    def get_symbols_for_file(self, snapshot_id: str, path: str) -> list[SymbolRecord]:
        rows = self.conn.execute(
            "SELECT symbol_id,name,qualified_name,kind,file_path,language,start_line,end_line,signature "
            "FROM symbols WHERE snapshot_id=? AND file_path=?", (snapshot_id, path)
        ).fetchall()
        return [SymbolRecord(*row) for row in rows]

    def get_call_sites_for_file(self, snapshot_id: str, path: str) -> list[tuple[str,str,str,int]]:
        return self.conn.execute(
            "SELECT source_id,target_name,evidence_path,evidence_line FROM call_sites "
            "WHERE snapshot_id=? AND evidence_path=?", (snapshot_id, path)
        ).fetchall()

    def commit_snapshot(self, snapshot_id: str, root: str, files: list[FileRecord],
                        symbols: list[SymbolRecord], call_sites: list[tuple[str,str,str,int]],
                        edges: list[EdgeRecord],
                        file_analysis: list[FileAnalysisRecord] | None = None,
                        imports: list[ImportRecord] | None = None,
                        references: list[ReferenceRecord] | None = None,
                        symbol_analysis: list[SymbolAnalysisRecord] | None = None) -> None:
        """Commit the entire graph atomically; a failed scan cannot leak partial data."""
        try:
            with self.conn:
                self.conn.execute("INSERT INTO snapshots(snapshot_id,root_path) VALUES(?,?)", (snapshot_id, root))
                self.conn.executemany("INSERT INTO files VALUES(?,?,?,?,?,?)", [
                    (snapshot_id,f.path,f.language,f.size_bytes,f.line_count,f.fingerprint) for f in files
                ])
                self.conn.executemany("INSERT INTO symbols VALUES(?,?,?,?,?,?,?,?,?,?)", [
                    (snapshot_id,s.symbol_id,s.name,s.qualified_name,s.kind,s.file_path,s.language,s.start_line,s.end_line,s.signature)
                    for s in symbols
                ])
                self.conn.executemany("INSERT INTO call_sites VALUES(?,?,?,?,?)", [
                    (snapshot_id,src,name,path,line) for src,name,path,line in call_sites
                ])
                self.conn.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", [
                    (snapshot_id,e.source_id,e.target_id,e.relation,e.resolution,e.evidence_path,e.evidence_line)
                    for e in edges
                ])
                self.conn.executemany(
                    "INSERT INTO symbol_fts(snapshot_id,symbol_id,name,qualified_name,signature,file_path) VALUES(?,?,?,?,?,?)",
                    [(snapshot_id,s.symbol_id,s.name,s.qualified_name,s.signature,s.file_path) for s in symbols]
                )
                self.conn.executemany(
                    "INSERT INTO file_analysis VALUES(?,?,?,?,?,?)",
                    [(snapshot_id,x.file_path,x.parser_backend,x.parse_status,x.error_count,x.parser_version)
                     for x in (file_analysis or [])]
                )
                self.conn.executemany(
                    "INSERT INTO imports VALUES(?,?,?,?,?,?,?,?)",
                    [(snapshot_id,x.file_path,x.module_specifier,x.imported_name,x.local_name,
                      x.import_kind,x.line,x.resolved_path) for x in (imports or [])]
                )
                self.conn.executemany(
                    "INSERT INTO symbol_references VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [(snapshot_id,x.source_id,x.target_name,x.receiver,x.syntax_kind,x.evidence_path,
                      x.evidence_line,x.start_byte,x.end_byte,x.resolution,x.target_id,
                      x.confidence,x.reason) for x in (references or [])]
                )
                self.conn.executemany(
                    "INSERT INTO symbol_analysis VALUES(?,?,?,?,?,?)",
                    [(snapshot_id,x.symbol_id,x.scope_name,x.signature_hash,x.body_hash,x.declaration_hash)
                     for x in (symbol_analysis or [])]
                )
    
        except sqlite3.IntegrityError:
            # Two readers may finish the same immutable snapshot concurrently.
            # The first committed transaction wins; the second safely reuses it.
            if self.has_snapshot(snapshot_id, root):
                return
            raise

    def get_file_analysis_map(self, snapshot_id: str) -> dict[str, FileAnalysisRecord]:
        rows = self.conn.execute(
            "SELECT path,parser_backend,parse_status,error_count,parser_version "
            "FROM file_analysis WHERE snapshot_id=?", (snapshot_id,)).fetchall()
        return {row[0]: FileAnalysisRecord(*row) for row in rows}

    def get_cached_file_data(self, snapshot_id: str, paths: list[str]) -> dict[str, dict]:
        """Batch-load reusable per-file data; avoids per-file SQL round trips on large projects."""
        result = {path: {"symbols": [], "call_sites": [], "imports": [],
                         "references": [], "symbol_analysis": [], "file_analysis": None}
                  for path in paths}
        for offset in range(0, len(paths), 400):
            chunk = paths[offset:offset + 400]
            if not chunk:
                continue
            marks = ",".join("?" for _ in chunk)
            args = (snapshot_id, *chunk)
            rows = self.conn.execute(
                "SELECT symbol_id,name,qualified_name,kind,file_path,language,start_line,end_line,signature "
                f"FROM symbols WHERE snapshot_id=? AND file_path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[4]]["symbols"].append(SymbolRecord(*row))
            rows = self.conn.execute(
                "SELECT source_id,target_name,evidence_path,evidence_line FROM call_sites "
                f"WHERE snapshot_id=? AND evidence_path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[2]]["call_sites"].append(tuple(row))
            rows = self.conn.execute(
                "SELECT file_path,module_specifier,imported_name,local_name,import_kind,line,resolved_path "
                f"FROM imports WHERE snapshot_id=? AND file_path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[0]]["imports"].append(ImportRecord(*row))
            rows = self.conn.execute(
                "SELECT source_id,target_name,receiver,syntax_kind,evidence_path,evidence_line,"
                "start_byte,end_byte,resolution,target_id,confidence,reason FROM symbol_references "
                f"WHERE snapshot_id=? AND evidence_path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[4]]["references"].append(ReferenceRecord(*row))
            rows = self.conn.execute(
                "SELECT s.file_path,a.symbol_id,a.scope_name,a.signature_hash,a.body_hash,a.declaration_hash "
                "FROM symbol_analysis a JOIN symbols s "
                "ON s.snapshot_id=a.snapshot_id AND s.symbol_id=a.symbol_id "
                f"WHERE a.snapshot_id=? AND s.file_path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[0]]["symbol_analysis"].append(SymbolAnalysisRecord(*row[1:]))
            rows = self.conn.execute(
                "SELECT path,parser_backend,parse_status,error_count,parser_version "
                f"FROM file_analysis WHERE snapshot_id=? AND path IN ({marks})", args).fetchall()
            for row in rows:
                result[row[0]]["file_analysis"] = FileAnalysisRecord(*row)
        return result

    def parser_coverage(self, snapshot_id: str) -> dict:
        backends = dict(self.conn.execute(
            "SELECT parser_backend,COUNT(*) FROM file_analysis WHERE snapshot_id=? GROUP BY parser_backend",
            (snapshot_id,)).fetchall())
        statuses = dict(self.conn.execute(
            "SELECT parse_status,COUNT(*) FROM file_analysis WHERE snapshot_id=? GROUP BY parse_status",
            (snapshot_id,)).fetchall())
        resolved = self.conn.execute(
            "SELECT resolution,COUNT(*) FROM symbol_references WHERE snapshot_id=? AND target_id!='' "
            "GROUP BY resolution", (snapshot_id,)).fetchall()
        unresolved = self.conn.execute(
            "SELECT COUNT(*) FROM symbol_references WHERE snapshot_id=? AND target_id=''",
            (snapshot_id,)).fetchone()[0]
        return {"files_by_backend":backends,"parse_status":statuses,
                "resolved_references":dict(resolved),"unresolved_references":unresolved,
                "tree_sitter_files":backends.get("tree_sitter",0)}

    def list_file_paths(self, snapshot_id: str) -> set[str]:
        return {row[0] for row in self.conn.execute(
            "SELECT path FROM files WHERE snapshot_id=?", (snapshot_id,)).fetchall()}

    def reverse_dependents(self, snapshot_id: str, start_ids: list[str],
                           max_depth: int = 3, max_nodes: int = 5000,
                           max_edges: int = 20000) -> dict:
        """Bounded multi-source reverse BFS with chunked SQL; avoids one query per changed symbol."""
        from collections import deque
        max_depth = max(0, min(int(max_depth), 10))
        max_nodes = max(1, min(int(max_nodes), 50000))
        max_edges = max(1, min(int(max_edges), 200000))
        frontier = deque(dict.fromkeys(start_ids))
        seen = set(frontier)
        output = []
        truncated = False
        for depth in range(1, max_depth + 1):
            if not frontier or truncated:
                break
            current = list(frontier)
            frontier.clear()
            next_nodes = []
            for offset in range(0, len(current), 400):
                chunk = current[offset:offset + 400]
                if not chunk:
                    continue
                marks = ",".join("?" for _ in chunk)
                remaining = max_edges - len(output)
                if remaining <= 0:
                    truncated = True
                    break
                rows = self.conn.execute(
                    "SELECT e.target_id,e.source_id,e.relation,e.resolution,e.evidence_path,"
                    "e.evidence_line,s.file_path,s.qualified_name,s.kind,s.start_line "
                    "FROM edges e JOIN symbols s ON s.snapshot_id=e.snapshot_id AND s.symbol_id=e.source_id "
                    f"WHERE e.snapshot_id=? AND e.target_id IN ({marks}) LIMIT ?",
                    (snapshot_id, *chunk, remaining + 1)).fetchall()
                if len(rows) > remaining:
                    rows = rows[:remaining]
                    truncated = True
                for target_id, source_id, relation, resolution, path, line, file_path, qname, kind, start_line in rows:
                    output.append({"from":target_id,"to":source_id,"relation":relation,
                                   "resolution":resolution,"evidence_path":path,
                                   "evidence_line":line,"depth":depth,
                                   "file_path":file_path,"qualified_name":qname,
                                   "kind":kind,"line":start_line})
                    if source_id not in seen:
                        if len(seen) >= max_nodes:
                            truncated = True
                        else:
                            seen.add(source_id)
                            next_nodes.append(source_id)
                if truncated:
                    break
            frontier.extend(next_nodes)
        return {"edges":output,"truncated":truncated,"visited_nodes":len(seen)}

    # Legacy helper methods retained for existing benchmark/tests.
    # Legacy helper methods retained for existing benchmark/tests.
    def create_snapshot(self, snapshot_id: str, root: str):
        self.conn.execute("INSERT OR REPLACE INTO snapshots(snapshot_id,root_path) VALUES(?,?)", (snapshot_id, root))
        self.conn.commit()
    def save_inventory(self, snapshot_id: str, files: list[FileRecord]):
        self.conn.executemany("INSERT OR REPLACE INTO files VALUES(?,?,?,?,?,?)", [
            (snapshot_id,f.path,f.language,f.size_bytes,f.line_count,f.fingerprint) for f in files])
        self.conn.commit()
    def save_symbols(self, snapshot_id: str, symbols: list[SymbolRecord]):
        self.conn.executemany("INSERT OR REPLACE INTO symbols VALUES(?,?,?,?,?,?,?,?,?,?)", [
            (snapshot_id,s.symbol_id,s.name,s.qualified_name,s.kind,s.file_path,s.language,s.start_line,s.end_line,s.signature) for s in symbols])
        self.conn.executemany("INSERT INTO symbol_fts(snapshot_id,symbol_id,name,qualified_name,signature,file_path) VALUES(?,?,?,?,?,?)", [
            (snapshot_id,s.symbol_id,s.name,s.qualified_name,s.signature,s.file_path) for s in symbols])
        self.conn.commit()
    def save_edges(self, snapshot_id: str, edges: list[EdgeRecord]):
        self.conn.executemany("INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?)", [
            (snapshot_id,e.source_id,e.target_id,e.relation,e.resolution,e.evidence_path,e.evidence_line) for e in edges])
        self.conn.commit()

    def overview(self, snapshot_id: str) -> dict:
        files = self.conn.execute("SELECT COUNT(*),COALESCE(SUM(line_count),0),COALESCE(SUM(size_bytes),0) FROM files WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        symbols = self.conn.execute("SELECT COUNT(*) FROM symbols WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0]
        edges = self.conn.execute("SELECT COUNT(*) FROM edges WHERE snapshot_id=?", (snapshot_id,)).fetchone()[0]
        langs = self.conn.execute("SELECT language,COUNT(*) FROM files WHERE snapshot_id=? GROUP BY language ORDER BY COUNT(*) DESC", (snapshot_id,)).fetchall()
        return {"files":files[0],"lines":files[1],"bytes":files[2],"symbols":symbols,"edges":edges,"languages":dict(langs)}

    def search(self, snapshot_id: str, query: str, limit: int = 20) -> list[dict]:
        if not query or limit < 1:
            return []
        query=query[:200]
        query_sql = "SELECT symbol_id,name,qualified_name,kind,file_path,start_line,signature FROM symbols WHERE snapshot_id=? AND "
        rows = self.conn.execute(query_sql + "name=? ORDER BY name LIMIT ?", (snapshot_id, query, limit)).fetchall()
        if not rows:
            rows = self.conn.execute(query_sql + "qualified_name=? ORDER BY name LIMIT ?", (snapshot_id, query, limit)).fetchall()
        if not rows:
            # Escape wildcard characters to keep user-supplied terms literal.
            term = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            rows = self.conn.execute(
                query_sql + "(name LIKE ? ESCAPE '\\' OR qualified_name LIKE ? ESCAPE '\\') ORDER BY name LIMIT ?",
                (snapshot_id, f"%{term}%", f"%{term}%", limit),
            ).fetchall()
        return [dict(zip(["symbol_id","name","qualified_name","kind","file_path","start_line","signature"],r)) for r in rows]

    def traverse(self, snapshot_id: str, symbol_id: str, direction: str = "forward",
                 max_depth: int = 3, max_nodes: int = 1000,
                 max_edges: int | None = None) -> list[dict]:
        """Bounded BFS; visited nodes prevent cycles and SQL LIMIT bounds high fan-out."""
        if direction not in {"forward","reverse"}:
            raise ValueError("direction must be forward or reverse")
        from collections import deque
        max_depth = max(0, min(int(max_depth), 20))
        max_nodes = max(1, min(int(max_nodes), 50000))
        max_edges = max_edges if max_edges is not None else max_nodes * 10
        max_edges = max(1, min(int(max_edges), 200000))
        col = "source_id" if direction == "forward" else "target_id"
        target = "target_id" if direction == "forward" else "source_id"
        frontier = deque([(symbol_id,0)])
        seen = {symbol_id}
        result = []
        edge_seen = set()
        while frontier and len(result) < max_edges:
            current, depth = frontier.popleft()
            if depth >= max_depth:
                continue
            remaining = max_edges - len(result)
            rows = self.conn.execute(
                f"SELECT {target},relation,resolution,evidence_path,evidence_line "
                f"FROM edges WHERE snapshot_id=? AND {col}=? LIMIT ?",
                (snapshot_id,current,remaining + 1)
            ).fetchall()
            if len(rows) > remaining:
                rows = rows[:remaining]
            for nxt,rel,res,path,line in rows:
                key = (current,nxt,rel,path,line)
                if key not in edge_seen:
                    edge_seen.add(key)
                    result.append({"from":current,"to":nxt,"relation":rel,"resolution":res,
                                   "evidence_path":path,"evidence_line":line,"depth":depth+1})
                if nxt not in seen and len(seen) < max_nodes:
                    seen.add(nxt)
                    frontier.append((nxt,depth+1))
            if len(result) >= max_edges:
                break
        return result
