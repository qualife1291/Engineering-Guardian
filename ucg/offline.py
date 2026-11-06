"""Offline-first codebase intelligence: navigation, prioritization, small context and diff.

Standard library only. No model, Git, network or application-code execution.
CALLS edges are heuristic candidates, not verified runtime dependencies.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
import re
from pathlib import PurePosixPath

from .store import UCGStore


def _limit(value: int, name: str, low: int, high: int) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be {low}..{high}")


def tree(store: UCGStore, snapshot: str, depth: int = 5, limit: int = 200) -> dict:
    _limit(depth, "depth", 1, 20)
    _limit(limit, "limit", 1, 1000)
    paths = [row[0] for row in store.conn.execute(
        "SELECT path FROM files WHERE snapshot_id=? ORDER BY path", (snapshot,))]
    entries, seen = [], set()
    for path in paths:
        parts = path.split("/")
        for i in range(1, min(len(parts), depth) + 1):
            prefix = "/".join(parts[:i])
            if prefix in seen:
                continue
            seen.add(prefix)
            entries.append({"path": prefix, "depth": i - 1,
                            "kind": "file" if i == len(parts) else "directory"})
            if len(entries) >= limit:
                break
        if len(entries) >= limit:
            break
    return {"snapshot_id": snapshot, "indexed_files": len(paths), "entries": entries,
            "top_level_counts": dict(Counter(p.split("/")[0] for p in paths).most_common(50)),
            "truncated": len(entries) >= limit,
            "notice": "Only permitted, recognized source files are counted."}


def outline(store: UCGStore, snapshot: str, path: str, limit: int = 120) -> dict:
    _limit(limit, "limit", 1, 300)
    if not isinstance(path, str) or not 0 < len(path) <= 4096:
        raise ValueError("path must be a relative indexed file name")
    path = path.replace("\\", "/")
    if path.startswith("/") or ":" in path or ".." in path.split("/") or str(PurePosixPath(path)) != path:
        raise ValueError("Unsafe/unnormalized relative file path")
    info = store.conn.execute(
        "SELECT language,line_count FROM files WHERE snapshot_id=? AND path=?",
        (snapshot, path)).fetchone()
    if info is None:
        raise KeyError("File not found in current index")
    rows = store.conn.execute(
        "SELECT symbol_id,qualified_name,kind,start_line,end_line,signature FROM symbols "
        "WHERE snapshot_id=? AND file_path=? ORDER BY start_line,symbol_id LIMIT ?",
        (snapshot, path, limit+1)).fetchall()
    return {"snapshot_id": snapshot, "file_path": path, "language": info[0], "lines": info[1],
            "symbols": [{"symbol_id": r[0], "name": r[1], "kind": r[2],
                         "line": r[3], "end_line": r[4],
                         "span": max(1,r[4]-r[3]+1), "signature": r[5][:240]}
                        for r in rows[:limit]], "truncated": len(rows)>limit,
            "notice": "Non-Python symbol boundaries use heuristic parsing."}


def hotspots(store: UCGStore, snapshot: str, min_lines: int = 300,
             min_function_lines: int = 80, limit: int = 30) -> dict:
    _limit(min_lines, "min_lines", 1, 100000)
    _limit(min_function_lines, "min_function_lines", 1, 100000)
    _limit(limit, "limit", 1, 100)
    files = store.conn.execute(
        "SELECT path,language,line_count FROM files WHERE snapshot_id=?",
        (snapshot,)).fetchall()
    spans = defaultdict(list)
    for path,name,start,end in store.conn.execute(
        "SELECT file_path,qualified_name,start_line,end_line FROM symbols "
        "WHERE snapshot_id=? AND kind IN ('function','method','procedure')", (snapshot,)):
        spans[path].append((max(1,end-start+1),name,start))
    ranked=[]
    for path,language,lines in files:
        funcs=spans.get(path,[])
        longest=max(funcs,default=(0,"",0))
        flags=[]
        if lines >= min_lines: flags.append("long_file")
        if longest[0] >= min_function_lines: flags.append("long_function")
        if lines >= max(min_lines,500) and len(funcs) <= 1: flags.append("few_detected_functions")
        if flags:
            score=lines/min_lines + longest[0]/min_function_lines + int(len(funcs)<=1)
            ranked.append({"file_path":path,"language":language,"lines":lines,
                           "functions":len(funcs),"longest_function":
                           {"name":longest[1],"line":longest[2],"lines":longest[0]} if longest[1] else None,
                           "signals":flags,"priority_score":round(score,3)})
    ranked.sort(key=lambda r:(-r["priority_score"],r["file_path"]))
    return {"snapshot_id":snapshot,"total_files":len(files),"flagged_files":len(ranked),
            "items":ranked[:limit],"truncated":len(ranked)>limit,
            "notice":"Structural maintenance signals, not proof of defects, poor formatting, missing docs or unsafe code."}


def _pagerank(paths: list[str], edges: list[tuple[str,str]]) -> dict[str,float]:
    """Damped random-walk centrality on a candidate FILE graph; 10 iterations."""
    if not paths: return {}
    paths=list(dict.fromkeys(paths))
    nodes=set(paths)
    outgoing=defaultdict(set)
    for a,b in edges:
        if a!=b and a in nodes and b in nodes: outgoing[a].add(b)
    n=len(paths); d=0.85
    rank={p:1/n for p in paths}
    for _ in range(10):
        dangling=sum(rank[p] for p in paths if not outgoing[p])
        new={p:(1-d)/n+d*dangling/n for p in paths}
        for p in paths:
            if outgoing[p]:
                share=d*rank[p]/len(outgoing[p])
                for target in outgoing[p]: new[target]+=share
        rank=new
    return rank


def repo_map(store: UCGStore, snapshot: str, focus: str = "",
             max_chars: int = 6000, limit: int = 80) -> dict:
    """Lexical matching + PageRank + per-file diversity, within a character budget.

    Ranking is an MMR-inspired greedy heuristic, not a globally optimal solver.
    Never reads code bodies or invokes an AI.
    """
    _limit(max_chars,"max_chars",256,32000)
    _limit(limit,"limit",1,500)
    if not isinstance(focus,str) or len(focus)>200: raise ValueError("focus too long")
    rows=store.conn.execute(
        "SELECT symbol_id,qualified_name,kind,file_path,start_line,signature "
        "FROM symbols WHERE snapshot_id=? ORDER BY file_path,start_line LIMIT 30001",
        (snapshot,)).fetchall()
    clipped=len(rows)>30000
    rows=rows[:30000]
    edges=store.conn.execute(
        "SELECT a.file_path,b.file_path,e.target_id FROM edges e "
        "JOIN symbols a ON a.snapshot_id=e.snapshot_id AND a.symbol_id=e.source_id "
        "JOIN symbols b ON b.snapshot_id=e.snapshot_id AND b.symbol_id=e.target_id "
        "WHERE e.snapshot_id=? LIMIT 100001", (snapshot,)).fetchall()
    clipped=clipped or len(edges)>100000
    edges=edges[:100000]
    paths=[r[0] for r in store.conn.execute(
        "SELECT path FROM files WHERE snapshot_id=?", (snapshot,))]
    ranks=_pagerank(paths,[(a,b) for a,b,_ in edges])
    incoming=Counter(sid for _,_,sid in edges)
    terms=re.findall(r"[a-z0-9_]+",focus.lower())[:12]
    ranked=[]
    for sid,name,kind,path,line,sig in rows:
        hay=(name+" "+path+" "+sig).lower()
        matches=sum(1 for term in terms if term in hay)
        score=7*matches + 2*math.log1p(incoming[sid]) + 75*ranks.get(path,0)
        if terms and matches==0: score*=0.1
        ranked.append((score,sid,name,kind,path,line,sig))
    ranked.sort(key=lambda x:(-x[0],x[4],x[5],x[2]))
    header="UCG REPO MAP | structural candidates (NOT exact impact)\n"
    header+=f"snapshot={snapshot}\n"
    if focus: header+=f"focus={focus}\n"
    chunks=[header]; used=len(header); chosen=set(); file_counts=Counter()
    for cap in (2,999999):
        for _,sid,name,kind,path,line,sig in ranked:
            if sid in chosen or file_counts[path]>=cap: continue
            label=f"- {path}:{line} [{kind}] {name}"
            if sig and sig!=name: label+=" | "+sig[:110].replace("\n"," ")
            label+="\n"
            if used+len(label)>max_chars: continue
            if len(chosen)>=limit: break
            chunks.append(label); used+=len(label); chosen.add(sid); file_counts[path]+=1
        if len(chosen)>=limit or max_chars-used<80: break
    out="".join(chunks)
    return {"snapshot_id":snapshot,"focus":focus,"text":out,
            "selected_symbols":len(chosen),"total_symbols_considered":len(rows),
            "max_chars":max_chars,"estimated_tokens_char_div_4":(len(out)+3)//4,
            "truncated":len(chosen)<len(rows) or clipped,
            "algorithm":"PageRank-like file centrality + lexical relevance + greedy file diversity",
            "notice":"Candidate calls are heuristics, not semantic facts; token estimate uses characters/4."}


def diff(store: UCGStore, root: str, base: str | None = None,
         head: str | None = None, limit: int = 100) -> dict:
    """Exact file content hashes; approximate definition/signature comparison."""
    _limit(limit,"limit",1,1000)
    snaps=[r[0] for r in store.conn.execute(
        "SELECT snapshot_id FROM snapshots WHERE root_path=? "
        "ORDER BY created_at DESC,rowid DESC LIMIT 500",(root,))]
    if not snaps: raise RuntimeError("No snapshot yet; run scan.")
    if head is None: head=snaps[0]
    if head not in snaps: raise ValueError("Head snapshot is outside authorized project")
    if base is None:
        idx=snaps.index(head)
        if idx+1>=len(snaps):
            return {"status":"no_baseline","base_snapshot":None,"head_snapshot":head,
                    "notice":"Only one snapshot. Edit source and scan again."}
        base=snaps[idx+1]
    if base not in snaps or base==head:
        raise ValueError("Base snapshot is invalid for this project")
    old=store.get_file_fingerprints(base)
    new=store.get_file_fingerprints(head)
    added=sorted(new.keys()-old.keys())
    removed=sorted(old.keys()-new.keys())
    changed=sorted(p for p in new.keys()&old.keys() if new[p]!=old[p])
    def definitions(s):
        return {(p,q,k):sig for p,q,k,sig in store.conn.execute(
            "SELECT file_path,qualified_name,kind,signature FROM symbols WHERE snapshot_id=?",(s,))}
    previous,current=definitions(base),definitions(head)
    created=sorted(current.keys()-previous.keys())
    deleted=sorted(previous.keys()-current.keys())
    signatures=sorted(k for k in previous.keys()&current.keys() if previous[k]!=current[k])
    possibly_changed=sorted(k for k in current if k[0] in changed)
    arrays=(added,removed,changed,created,deleted,signatures,possibly_changed)
    return {"status":"compared","base_snapshot":base,"head_snapshot":head,
            "counts":{"added_files":len(added),"deleted_files":len(removed),
                      "modified_files":len(changed),"added_symbols":len(created),
                      "deleted_symbols":len(deleted),"signature_changes":len(signatures),
                      "possible_function_body_changes":len(possibly_changed)},
            "added_files":added[:limit],"deleted_files":removed[:limit],
            "modified_files":changed[:limit],"added_symbols":created[:limit],
            "deleted_symbols":deleted[:limit],"signature_changes":signatures[:limit],
            "possibly_changed_symbols":possibly_changed[:limit],
            "truncated":any(len(a)>limit for a in arrays),
            "notice":"Hashes detect exact file changes. Body/behavior is NOT semantically compared."}


def brief(overview: dict, filesystem: dict, hot: dict, mapping: dict) -> str:
    """Generate an offline Markdown brief in memory; caller decides where to save."""
    lines=["# Engineering Guardian — Offline Codebase Brief","",
           "## Source inventory","",
           f"- Snapshot: {overview['snapshot_id']}",
           f"- Files: {overview['files']} | Lines: {overview['lines']} | Symbols: {overview['symbols']}",
           f"- Heuristic CALLS edges: {overview['edges']}",
           "- Languages: "+", ".join(f"{k} ({v})" for k,v in overview["languages"].items()),
           "","## Top-level structure",""]
    for name,count in filesystem["top_level_counts"].items():
        lines.append(f"- {name}: {count} source files")
    lines.extend(["","## Files to inspect first",""])
    for f in hot["items"]:
        lines.append(f"- {f['file_path']}: {f['lines']} lines; {', '.join(f['signals'])}")
    if not hot["items"]: lines.append("- No files over thresholds.")
    lines.extend(["","## Ranked symbol navigation","","~~~text",mapping["text"].rstrip(),"~~~",
                  "","## Limitations","",
                  "- Source is not executed, no AI/network requests are made.",
                  "- Non-Python parsers and all call links are heuristic candidates.",
                  "- Long files are not automatically low quality; no doc/formatting audit is implied.",
                  "- No runtime impact or semantic equivalence guarantee.",""])
    return "\n".join(lines)
