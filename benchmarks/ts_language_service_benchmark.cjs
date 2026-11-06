const ts = require('typescript');
const fs = require('fs');
const path = require('path');

const root = path.resolve(process.argv[2] || '.benchmark/valid-100');
const files = [];
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full);
    else if (full.endsWith('.ts')) files.push(full);
  }
}
walk(root);
const options = { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.ESNext, strict: false };
const host = {
  getCompilationSettings: () => options,
  getScriptFileNames: () => files,
  getScriptVersion: () => '0',
  getScriptSnapshot: file => fs.existsSync(file) ? ts.ScriptSnapshot.fromString(fs.readFileSync(file, 'utf8')) : undefined,
  getCurrentDirectory: () => root,
  getDefaultLibFileName: opts => ts.getDefaultLibFilePath(opts),
  fileExists: fs.existsSync,
  readFile: file => fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : undefined,
  readDirectory: ts.sys.readDirectory,
};
const service = ts.createLanguageService(host);
const file = files.find(f => f.endsWith('typescript_016.ts'));
const source = fs.readFileSync(file, 'utf8');
const symbol = 'normalize_typescript_016_10';
const position = source.indexOf(symbol);
const samples = [];
let started = process.hrtime.bigint();
let result = service.findReferences(file, position);
const coldMs = Number(process.hrtime.bigint() - started) / 1e6;
for (let i = 0; i < 100; i++) {
  started = process.hrtime.bigint();
  result = service.findReferences(file, position);
  samples.push(Number(process.hrtime.bigint() - started) / 1e6);
}
samples.sort((a, b) => a - b);
const refs = (result || []).flatMap(group => group.references);
console.log(JSON.stringify({
  tool: 'TypeScript Language Service',
  version: ts.version,
  source_files: files.length,
  symbol,
  cold_first_query_ms: coldMs,
  warm_query_median_ms: samples[49],
  warm_query_p95_ms: samples[94],
  warm_runs: samples.length,
  reference_count_including_definition: refs.length,
  references: refs.map(ref => ({ file: ref.fileName, line: sourceLine(ref.fileName, ref.textSpan.start), isDefinition: ref.isDefinition })),
}, null, 2));
function sourceLine(fileName, offset) {
  const text = fs.readFileSync(fileName, 'utf8');
  return text.slice(0, offset).split('\n').length;
}
