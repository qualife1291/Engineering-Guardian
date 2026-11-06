from __future__ import annotations
import json, statistics, sys, time
from pathlib import Path
import jedi

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.benchmark/valid-100').resolve()
file = next(root.rglob('python_075.py'))
source = file.read_text()
symbol = 'normalize_python_075_10'
offset = source.index(symbol)
line = source.count('\n', 0, offset) + 1
column = offset - source.rfind('\n', 0, offset) - 1
project = jedi.Project(path=str(root))
started = time.perf_counter()
script = jedi.Script(code=source, path=str(file), project=project)
refs = script.get_references(line=line, column=column, scope='project')
cold_ms = (time.perf_counter() - started) * 1000
samples = []
for _ in range(100):
    started = time.perf_counter()
    refs = script.get_references(line=line, column=column, scope='project')
    samples.append((time.perf_counter() - started) * 1000)
sorted_samples = sorted(samples)
print(json.dumps({
    'tool': 'Jedi',
    'version': jedi.__version__,
    'project_root': str(root),
    'symbol': symbol,
    'cold_first_query_ms': cold_ms,
    'warm_query_median_ms': statistics.median(samples),
    'warm_query_p95_ms': sorted_samples[94],
    'warm_runs': len(samples),
    'reference_count_including_definition': len(refs),
    'references': [{'file': str(r.module_path), 'line': r.line, 'column': r.column} for r in refs],
}, indent=2))
