"""SQLite persistence for versioned, immutable source-code snapshots.

SQLite lives outside the target project by default. All writes to a new
snapshot are committed as a single transaction, making partial scans invisible.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from .models import FileRecord, SymbolRecord, EdgeRecord

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
                        edges: list[EdgeRecord]) -> None:
        """Commit the entire graph atomically; a failed scan cannot leak partial data."""
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
                 max_depth: int = 3, max_nodes: int = 1000) -> list[dict]:
        if direction not in {"forward","reverse"}:
            raise ValueError("direction must be forward or reverse")
        from collections import deque
        col = "source_id" if direction == "forward" else "target_id"
        target = "target_id" if direction == "forward" else "source_id"
        frontier = deque([(symbol_id,0)])
        seen = {symbol_id}
        result=[]
        while frontier and len(seen) <= max_nodes:
            current, depth = frontier.popleft()
            if depth >= max_depth: continue
            rows = self.conn.execute(
                f"SELECT {target},relation,resolution,evidence_path,evidence_line FROM edges WHERE snapshot_id=? AND {col}=?",
                (snapshot_id,current)
            ).fetchall()
            for nxt,rel,res,path,line in rows:
                result.append({"from":current,"to":nxt,"relation":rel,"resolution":res,
                               "evidence_path":path,"evidence_line":line,"depth":depth+1})
                if nxt not in seen and len(seen) < max_nodes:
                    seen.add(nxt)
                    frontier.append((nxt,depth+1))
        return result
