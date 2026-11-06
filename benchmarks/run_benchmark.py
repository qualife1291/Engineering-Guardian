from __future__ import annotations
import argparse, json, time, statistics, resource
from pathlib import Path
from ucg.engine import scan_workspace
from ucg.store import UCGStore
from ucg.context import build_context_pack

def approx_tokens(text:str)->int:
    # Coarse estimate only; not a model tokenizer.
    return max(1,(len(text)+3)//4)

def percentile(values, pct):
    ordered=sorted(values)
    if not ordered: return None
    idx=min(len(ordered)-1, max(0, round((pct/100)*(len(ordered)-1))))
    return ordered[idx]

def full_context_read(root:Path):
    started=time.perf_counter(); texts=[]; line_count=0
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix in {".py",".ts",".kt",".dart",".sql"}:
            content=path.read_text(encoding="utf-8",errors="replace")
            texts.append(content); line_count += len(content.splitlines())
    corpus="\n".join(texts)
    return {"seconds":time.perf_counter()-started,"files":len(texts),"characters":len(corpus),"bytes":len(corpus.encode()),"lines":line_count,"approx_tokens_char_div_4":approx_tokens(corpus)}

def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--output",default="benchmark-results.json");p.add_argument("--db",default=".benchmark/ucg.sqlite");p.add_argument("--runs",type=int,default=5);a=p.parse_args()
    root=Path(a.source).resolve(); full_reads=[]; cold=[]; search_ms=[]; graph_ms=[]; context_ms=[]; context_tokens=[]; overviews=[]; timings=[]
    for i in range(a.runs):
        full_reads.append(full_context_read(root))
        db=Path(a.db); db.parent.mkdir(parents=True,exist_ok=True)
        if db.exists(): db.unlink()
        for suffix in ("-wal","-shm"): Path(str(db)+suffix).unlink(missing_ok=True)
        started=time.perf_counter(); result=scan_workspace(str(root),str(db),snapshot_id=f"cold_{i}"); cold.append(time.perf_counter()-started)
        overviews.append(result["overview"]); timings.append(result["timings_seconds"])
        store=UCGStore(db)
        hits=store.search(f"cold_{i}","operation_1",limit=20)
        for _ in range(100):
            t=time.perf_counter(); store.search(f"cold_{i}","operation_1",limit=20); search_ms.append((time.perf_counter()-t)*1000)
        if hits:
            for _ in range(100):
                t=time.perf_counter(); store.traverse(f"cold_{i}",hits[0]["symbol_id"],"forward",max_depth=4,max_nodes=500); graph_ms.append((time.perf_counter()-t)*1000)
        store.close()
        for _ in range(10):
            t=time.perf_counter(); pack=build_context_pack(str(db),f"cold_{i}","operation_1",max_chars=32000); context_ms.append((time.perf_counter()-t)*1000); context_tokens.append(pack["estimated_tokens_char_div_4"])
    latest=overviews[-1]
    report={
      "benchmark":"100-file / 100k-line source understanding preparation benchmark",
      "dataset":{"root":str(root),"source_files":latest["files"],"source_lines":latest["lines"],"languages":latest["languages"]},
      "chatgpt_full_context_baseline":{"read_seconds_median":statistics.median(x["seconds"] for x in full_reads),"payload_files":full_reads[-1]["files"],"payload_lines":full_reads[-1]["lines"],"payload_bytes":full_reads[-1]["bytes"],"approx_tokens_char_div_4":full_reads[-1]["approx_tokens_char_div_4"],"status":"input preparation measured; actual ChatGPT inference latency and correctness were not measured"},
      "engineering_guardian_python_poc":{"cold_index_seconds_median":statistics.median(cold),"cold_index_seconds_runs":cold,"symbol_search_ms_median":statistics.median(search_ms),"symbol_search_ms_p95":percentile(search_ms,95),"graph_query_ms_median":statistics.median(graph_ms) if graph_ms else None,"graph_query_ms_p95":percentile(graph_ms,95) if graph_ms else None,"context_pack_ms_median":statistics.median(context_ms),"context_pack_ms_p95":percentile(context_ms,95),"context_pack_estimated_tokens_median":statistics.median(context_tokens),"last_stage_timings_seconds":timings[-1],"overview":latest,"process_peak_rss_kb":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"implementation":"dependency-free Python prototype; not the planned Rust/Tree-sitter/SCIP engine"},
      "comparison":{"finding":"The prototype prepares a searchable local index in seconds for this synthetic fixture, while a full-context workflow must ingest approximately the entire source payload. This does not prove the prototype is faster than ChatGPT end-to-end because actual model inference, upload and answer latency were not run here.","fair_test_required":"Run identical questions against (A) ChatGPT supplied with all source and (B) UCG context-pack retrieval; score wall-clock time, time-to-first-useful-answer, answer correctness, impact recall and input tokens over at least five runs."},
      "limitations":["Non-Python extraction uses regex/brace heuristics, not Tree-sitter.","Edges are AST/name candidates, not compiler-verified call edges.","SCIP and cross-language contract resolution are not implemented.","Incremental re-indexing is not implemented; repeated cold scans were measured.","Character/4 is a rough token estimate, not an exact tokenizer count."]
    }
    Path(a.output).parent.mkdir(parents=True,exist_ok=True);Path(a.output).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
