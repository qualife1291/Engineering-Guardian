from __future__ import annotations
import argparse, json, os, shutil, statistics, subprocess, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ucg.engine import scan_workspace
from ucg.store import UCGStore
from ucg.context import build_context_pack

EXT_GLOBS = ["*.py", "*.ts", "*.kt", "*.dart", "*.sql"]
QUERY = "python_075_operation_9"
CALL_QUERY = "normalize_python_075_10("

def p95(xs):
    s=sorted(xs)
    return s[min(len(s)-1, max(0, int(round(.95*(len(s)-1)))))] if s else None

def timed_command(cmd, cwd, runs=25):
    samples=[]; last=None
    for _ in range(runs):
        t=time.perf_counter()
        cp=subprocess.run(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        dt=(time.perf_counter()-t)*1000
        if cp.returncode != 0:
            raise RuntimeError(f"command failed {cmd}: {cp.stderr[:500]}")
        samples.append(dt); last=cp.stdout
    return {"median_ms":statistics.median(samples),"p95_ms":p95(samples),"runs":runs,"output_lines":len(last.splitlines()),"sample":last.splitlines()[:3]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--runs',type=int,default=25)
    a=p.parse_args()
    root=Path(a.source).resolve()
    work=root.parent / 'git-valid-100'
    static_root=root.parent.parent.parent / 'engineering-guardian-static-valid-100'
    if work.exists(): shutil.rmtree(work)
    if static_root.exists(): shutil.rmtree(static_root)
    shutil.copytree(root,work,ignore=shutil.ignore_patterns('.git'))
    shutil.copytree(root,static_root,ignore=shutil.ignore_patterns('.git'))
    subprocess.run(['git','init','-q'],cwd=work,check=True)
    subprocess.run(['git','config','user.email','benchmark@example.invalid'],cwd=work,check=True)
    subprocess.run(['git','config','user.name','Benchmark'],cwd=work,check=True)
    subprocess.run(['git','add','.'],cwd=work,check=True)
    subprocess.run(['git','commit','-qm','Add valid benchmark fixture'],cwd=work,check=True)

    rg_inventory=timed_command(['rg','--files','-g','*.py','-g','*.ts','-g','*.kt','-g','*.dart','-g','*.sql'],root,a.runs)
    git_inventory=timed_command(['git','ls-files','*.py','*.ts','*.kt','*.dart','*.sql'],work,a.runs)
    find_inventory=timed_command(['bash','-lc',"find . -type f \\( -name '*.py' -o -name '*.ts' -o -name '*.kt' -o -name '*.dart' -o -name '*.sql' \\) -print | sort"],root,a.runs)

    rg_symbol=timed_command(['rg','-n','-F','--hidden','-g','*.py','-g','*.ts','-g','*.kt','-g','*.dart','-g','*.sql',QUERY,'.'],root,a.runs)
    git_symbol=timed_command(['git','grep','-n','-F','--',QUERY,'--','*.py','*.ts','*.kt','*.dart','*.sql'],work,a.runs)
    git_noindex_symbol=timed_command(['git','grep','--no-index','-n','-F','--',QUERY,static_root.name],static_root.parent,a.runs)
    rg_static_symbol=timed_command(['rg','-n','-F','--hidden','-g','*.py','-g','*.ts','-g','*.kt','-g','*.dart','-g','*.sql',QUERY,static_root.name],static_root.parent,a.runs)
    git_cached=timed_command(['git','grep','--cached','-n','-F','--',QUERY,'--','*.py','*.ts','*.kt','*.dart','*.sql'],work,a.runs)
    grep_symbol=timed_command(['grep','-R','-n','-F','--include=*.py','--include=*.ts','--include=*.kt','--include=*.dart','--include=*.sql',QUERY,'.'],root,a.runs)

    rg_call=timed_command(['rg','-n','-F','--hidden','-g','*.py','-g','*.ts','-g','*.kt','-g','*.dart','-g','*.sql',CALL_QUERY,'.'],root,a.runs)
    git_call=timed_command(['git','grep','-n','-F','--',CALL_QUERY,'--','*.py','*.ts','*.kt','*.dart','*.sql'],work,a.runs)

    # UCG cold indexing on the same valid source tree.
    cold=[]; latest=None; db=root.parent/'ucg-valid-bench.sqlite'
    for i in range(5):
        if db.exists(): db.unlink()
        for suffix in ('-wal','-shm'): Path(str(db)+suffix).unlink(missing_ok=True)
        t=time.perf_counter(); latest=scan_workspace(str(root),str(db),snapshot_id=f'valid_{i}'); cold.append((time.perf_counter()-t)*1000)
    snapshot=latest['snapshot_id']
    store=UCGStore(db)
    hits=store.search(snapshot,QUERY,limit=20)
    if not hits:
        raise RuntimeError(f'UCG did not find {QUERY}; index overview={latest["overview"]}')
    sym_id=hits[0]['symbol_id']
    search=[]; traverse=[]
    graph_result=store.traverse(snapshot,sym_id,'forward',max_depth=2,max_nodes=100)
    for _ in range(a.runs*4):
        t=time.perf_counter(); store.search(snapshot,QUERY,limit=20); search.append((time.perf_counter()-t)*1000)
        t=time.perf_counter(); store.traverse(snapshot,sym_id,'forward',max_depth=2,max_nodes=100); traverse.append((time.perf_counter()-t)*1000)
    pack_times=[]; pack=None
    for _ in range(a.runs):
        t=time.perf_counter(); pack=build_context_pack(str(db),snapshot,QUERY,max_chars=32000); pack_times.append((time.perf_counter()-t)*1000)
    store.close()

    report={
      'benchmark':'existing local code tools vs Engineering Guardian on valid synthetic fixture',
      'fixture':{'source_files':100,'lines_per_file':1000,'source_lines':100000,'languages':{'python':20,'typescript':20,'kotlin':20,'dart':20,'sql':20},'syntax_validation':{'python_ast':'pass','typescript_tsc':'pass','kotlin_compiler':'pass','sqlite_sql':'pass','dart':'not validated (SDK unavailable)'}},
      'environment':{'ripgrep':subprocess.run(['rg','--version'],capture_output=True,text=True).stdout.splitlines()[0],'git':subprocess.run(['git','--version'],capture_output=True,text=True).stdout.strip(),'python':sys.version.split()[0],'tsc':subprocess.run(['tsc','--version'],capture_output=True,text=True).stdout.strip(),'kotlinc':subprocess.run(['kotlinc','-version'],capture_output=True,text=True).stderr.strip().splitlines()[-1] if subprocess.run(['kotlinc','-version'],capture_output=True,text=True).stderr else 'available'},
      'query':{'unique_symbol':QUERY,'call_reference':CALL_QUERY,'runs_per_external_command':a.runs},
      'inventory':{'ripgrep_rg_files':rg_inventory,'git_ls_files':git_inventory,'find':find_inventory},
      'literal_symbol_search':{'ripgrep':rg_symbol,'git_grep_worktree':git_symbol,'git_grep_cached_index':git_cached,'git_grep_no_index_static_folder_outside_git':git_noindex_symbol,'ripgrep_static_folder_outside_git':rg_static_symbol,'gnu_grep_recursive':grep_symbol,'guardian_sql_search':{'median_ms':statistics.median(search),'p95_ms':p95(search),'runs':len(search),'result_count':len(hits),'first_result':hits[0]}},
      'call_reference_search':{'ripgrep':rg_call,'git_grep_worktree':git_call,'guardian_graph_traverse':{'median_ms':statistics.median(traverse),'p95_ms':p95(traverse),'runs':len(traverse),'edge_count':len(graph_result),'edges':graph_result}},
      'guardian':{'cold_index_ms_runs':cold,'cold_index_ms_median':statistics.median(cold),'overview':latest['overview'],'timings_seconds':latest['timings_seconds'],'context_pack_ms_median':statistics.median(pack_times),'context_pack_ms_p95':p95(pack_times),'context_pack_estimated_tokens':pack['estimated_tokens_char_div_4'],'context_pack_chars':pack['context_characters'],'context_pack_source_snippet_characters':pack['source_snippet_characters']},
      'tools_not_installed':{'universal_ctags':'not installed','tree_sitter_cli_and_python_bindings':'not installed','scip_indexers':'not installed','semgrep':'not installed','ast_grep':'not installed'},
      'interpretation':[
        'ripgrep and git grep are literal text-search tools; they do not provide compiler-accurate call graphs or impact closure.',
        'Guardian adds a persisted symbol inventory, candidate call edges and query-specific context packing, but its current cross-language edges are heuristic and must not be treated as precise navigation.',
        'This is a synthetic fixture benchmark; it does not measure real-repository correctness or end-to-end LLM answer time.'
      ]
    }
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
