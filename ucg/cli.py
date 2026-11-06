"""Non-interactive CLI for local CI, developers and Claude Code troubleshooting."""
from __future__ import annotations
import argparse
import json
import sys
from .service import GuardianService
from .diagnostics import diagnostic_summary


def main() -> int:
    p=argparse.ArgumentParser(prog="guardian",description="Engineering Guardian POC v0.4 (local, read-only source indexing)")
    p.add_argument("--root",default=".",help="Authorized project folder; defaults to current directory")
    p.add_argument("--db",default=None,help="SQLite path; default is external ~/.engineering-guardian/indexes")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("scan",help="Index or incrementally refresh a local folder")
    sub.add_parser("status",help="Check snapshot and source freshness")
    sub.add_parser("overview",help="Summarize indexed project")
    find=sub.add_parser("search",help="Find code symbols")
    find.add_argument("query")
    find.add_argument("--limit",type=int,default=20)
    callers=sub.add_parser("callers",help="Find heuristic callers by symbol ID")
    callers.add_argument("symbol_id"); callers.add_argument("--depth",type=int,default=2)
    callees=sub.add_parser("callees",help="Find heuristic callees by symbol ID")
    callees.add_argument("symbol_id"); callees.add_argument("--depth",type=int,default=2)
    context=sub.add_parser("context",help="Produce bounded source context for AI")
    context.add_argument("query"); context.add_argument("--max-chars",type=int,default=12000)
    tree=sub.add_parser("tree",help="Browse compact source-folder tree (offline)")
    tree.add_argument("--depth",type=int,default=5)
    tree.add_argument("--limit",type=int,default=200)
    outline=sub.add_parser("outline",help="List definitions in one large file")
    outline.add_argument("file",help="Relative indexed path (use tree for paths)")
    outline.add_argument("--limit",type=int,default=120)
    hot=sub.add_parser("hotspots",help="Find long files and functions (structural only)")
    hot.add_argument("--min-lines",type=int,default=300)
    hot.add_argument("--min-function-lines",type=int,default=80)
    hot.add_argument("--limit",type=int,default=30)
    mapping=sub.add_parser("repo-map",help="Ranked symbol map, no AI or source bodies")
    mapping.add_argument("--focus",default="")
    mapping.add_argument("--max-chars",type=int,default=6000)
    mapping.add_argument("--limit",type=int,default=80)
    mapping.add_argument("--text",action="store_true",help="Print map directly instead of JSON")
    versions=sub.add_parser("diff",help="Compare two stored snapshots without Git")
    versions.add_argument("--base",default=None)
    versions.add_argument("--head",default=None)
    versions.add_argument("--limit",type=int,default=100)
    short=sub.add_parser("brief",help="Build offline Markdown architecture brief (stdout only)")
    short.add_argument("--focus",default="")
    short.add_argument("--max-chars",type=int,default=6000)
    short.add_argument("--format",choices=["json","markdown"],default="json")
    sub.add_parser("support-bundle",help="Export privacy-filtered diagnostic ZIP to share for upgrades")
    sub.add_parser("log-summary",help="Aggregate anonymous quality/performance diagnostic metrics")
    sub.add_parser("doctor",help="Inspect local environment and index health")
    args=p.parse_args()
    try:
        service=GuardianService(args.root,args.db)
        if args.command=="scan":result=service.scan()
        elif args.command=="status":result=service.status()
        elif args.command=="overview":result=service.overview()
        elif args.command=="search":result=service.find_symbol(args.query,args.limit)
        elif args.command=="callers":result=service.relations(args.symbol_id,"reverse",args.depth)
        elif args.command=="callees":result=service.relations(args.symbol_id,"forward",args.depth)
        elif args.command=="context":result=service.context(args.query,args.max_chars)
        elif args.command=="tree":result=service.tree(args.depth,args.limit)
        elif args.command=="outline":result=service.outline(args.file,args.limit)
        elif args.command=="hotspots":result=service.hotspots(args.min_lines,args.min_function_lines,args.limit)
        elif args.command=="repo-map":result=service.repo_map(args.focus,args.max_chars,args.limit)
        elif args.command=="diff":result=service.diff(args.base,args.head,args.limit)
        elif args.command=="brief":result=service.brief(args.focus,args.max_chars)
        elif args.command=="support-bundle":result=service.support_log()
        elif args.command=="log-summary":result=diagnostic_summary(service.root)
        elif args.command=="doctor":
            from . import __version__
            result={"guardian_version":__version__,"python_version":sys.version.split()[0],
                    "read_only_source":True,"mcp":"stdio, JSON-RPC 2.0, no external packages",
                    "current_status":service.status(),
                    "parser_limitation":"Python AST; other languages heuristic (not Tree-sitter/SCIP)",
                    "diagnostic_bundle_command":"python -m ucg.cli --root <project> support-bundle"}
        else:raise AssertionError("unexpected command")
        if args.command=="repo-map" and args.text: print(result["text"],end="")
        elif args.command=="brief" and args.format=="markdown": print(result["markdown"])
        else: print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        return 0
    except Exception as exc:
        # CLI may be used by humans; avoid dumping absolute source paths or code.
        print(json.dumps({"error":type(exc).__name__,"hint":"Check workspace, run scan, then doctor/support-bundle"}),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
