from __future__ import annotations
import json, statistics, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ucg.store import UCGStore

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.benchmark/valid-100').resolve()
repo = Path(__file__).resolve().parents[1]
report_dir = repo / 'reports'
report_dir.mkdir(exist_ok=True)

def run_json(command):
    cp = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=True)
    return json.loads(cp.stdout)

jedi = run_json([sys.executable, str(repo/'benchmarks/jedi_reference_benchmark.py'), str(root)])
ts = run_json(['node', str(repo/'benchmarks/ts_language_service_benchmark.cjs'), str(root)])
store = UCGStore(root.parent/'ucg-valid-bench.sqlite')
snapshot = 'valid_4'
ucg_results = {}
for symbol, language in [('normalize_python_075_10','Python'), ('normalize_typescript_016_10','TypeScript')]:
    hit = store.search(snapshot, symbol, limit=10)[0]
    values=[]
    result=store.traverse(snapshot, hit['symbol_id'], 'reverse', max_depth=1, max_nodes=100)
    for _ in range(100):
        t=time.perf_counter_ns(); store.traverse(snapshot,hit['symbol_id'],'reverse',max_depth=1,max_nodes=100); values.append((time.perf_counter_ns()-t)/1e6)
    values.sort()
    ucg_results[language] = {
        'symbol': symbol,
        'warm_query_median_ms': statistics.median(values),
        'warm_query_p95_ms': values[94],
        'warm_runs': len(values),
        'reference_edge_count_excluding_definition': len(result),
        'references': [{'file':e['evidence_path'],'line':e['evidence_line']} for e in result],
        'resolution': 'ast_candidate; heuristic, not compiler verified'
    }
store.close()
report = {
    'benchmark': 'Language-native references vs Guardian reverse graph',
    'fixture': {'source_files':100,'lines_per_file':1000,'total_lines':100000,'languages':['Python','TypeScript','Kotlin','Dart','SQL']},
    'python': {'jedi':jedi,'guardian':ucg_results['Python']},
    'typescript': {'typescript_language_service':ts,'guardian':ucg_results['TypeScript']},
    'fairness_notes': [
        'Each language-native tool only analyzes its own language subset; this is not a 100-file all-language comparison.',
        'Cold first-query times include language-service initialization and are not directly comparable with Guardian cold indexing of all five languages.',
        'Warm query results are for same-file synthetic references; cross-module and dynamic dispatch accuracy require separate real-project tests.',
        'Guardian edges are heuristic candidates and must be verified before claiming semantic equivalence.'
    ]
}
out = report_dir/'language-service-comparison-valid-100.json'
out.write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
