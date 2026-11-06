"""Snapshot-safe bounded source context extraction; fail closed if source changed."""
from __future__ import annotations
import json
from pathlib import Path
from .scanner import MAX_FILE_BYTES, fingerprint, read_bounded_regular_file
from .store import UCGStore

class StaleSnapshotError(RuntimeError):
    """The current source contents do not match the indexed snapshot."""


def build_context_pack(db_path: str, snapshot_id: str, query: str, max_chars: int = 32000, limit: int = 30):
    if max_chars < 256 or max_chars > 100_000:
        raise ValueError("max_chars must be between 256 and 100000")
    store=UCGStore(db_path)
    try:
        row=store.conn.execute("SELECT root_path FROM snapshots WHERE snapshot_id=?",(snapshot_id,)).fetchone()
        if not row:
            raise KeyError("Unknown snapshot")
        root=Path(row[0]).resolve()
        hits=store.search(snapshot_id,query,min(limit,30))
        items=[]; used=0
        for hit in hits:
            raw_path=root/hit["file_path"]
            path=raw_path.resolve()
            if raw_path.is_symlink() or not path.is_relative_to(root):
                raise StaleSnapshotError("File path no longer belongs to the indexed workspace; run scan again")
            stored=store.conn.execute("SELECT fingerprint FROM files WHERE snapshot_id=? AND path=?",
                                      (snapshot_id,hit["file_path"])).fetchone()
            if not stored:
                raise StaleSnapshotError("Indexed file missing; run scan again")
            try:
                data, _ = read_bounded_regular_file(path, MAX_FILE_BYTES)
                if data is None:
                    raise StaleSnapshotError("Source exceeds the indexed size limit; run scan again")
            except (OSError, ValueError) as exc:
                raise StaleSnapshotError("Source unavailable or no longer a regular file; run scan again") from exc
            if fingerprint(data)!=stored[0]:
                raise StaleSnapshotError("Source has changed since snapshot; run scan again")
            lines=data.decode("utf-8",errors="replace").splitlines()
            start=max(1,hit["start_line"]-5); end=min(len(lines),hit["start_line"]+35)
            snippet="\n".join(f"{n}: {lines[n-1]}" for n in range(start,end+1))
            item={**hit,"start_context_line":start,"end_context_line":end,"snippet":snippet,
                  "evidence_fingerprint":stored[0]}
            cost=len(json.dumps(item,ensure_ascii=False))
            if used+cost>max_chars:
                break
            items.append(item); used+=cost
        serialized=json.dumps(items,ensure_ascii=False)
        return {"snapshot_id":snapshot_id,"query":query,"symbols":items,
                "source_snippet_characters":sum(len(x["snippet"]) for x in items),
                "context_characters":len(serialized),"estimated_tokens_char_div_4":(len(serialized)+3)//4,
                "max_chars":max_chars,"truncated":len(items)<len(hits),
                "resolution_notice":"Tree-sitter edges are conservative syntax bindings; fallback ast_candidate edges are heuristic. Neither is compiler/type-checker or runtime proof."}
    finally:
        store.close()
