"""Minimal MCP stdio server for Claude Code; Python 3.11+, no third-party deps.

MCP transport protocol: one JSON-RPC message per UTF-8 line. This program
writes protocol messages ONLY to stdout. No shell tools and no source writes.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from typing import Any
from . import __version__
from .service import GuardianService

TOOL_LIST=[
    {"name":"guardian_scan", "description":"Build or refresh a versioned graph index for the authorized project. Reads source; only writes cache outside the project. CALLS edges are heuristic candidates.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"guardian_index_status", "description":"Show index freshness, snapshot and coverage; never return source content.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"guardian_overview", "description":"Report file, line, symbol, edge and language counts. Refuses stale indexes.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
    {"name":"guardian_find_symbol", "description":"Find symbol definitions by exact/substring name; use a narrow search before requesting context.",
     "inputSchema":{"type":"object","properties":{"query":{"type":"string","minLength":1,"maxLength":200},
                                        "limit":{"type":"integer","minimum":1,"maximum":40}},"required":["query"],"additionalProperties":False}},
    {"name":"guardian_get_callers", "description":"Trace candidate callers for a symbol ID; requires current index and verified source freshness.",
     "inputSchema":{"type":"object","properties":{"symbol_id":{"type":"string","minLength":1,"maxLength":512},
                                        "depth":{"type":"integer","minimum":1,"maximum":4}},"required":["symbol_id"],"additionalProperties":False}},
    {"name":"guardian_get_callees", "description":"Trace candidate callees for a symbol ID; all CALLS edges are heuristic until semantic resolver is integrated.",
     "inputSchema":{"type":"object","properties":{"symbol_id":{"type":"string","minLength":1,"maxLength":512},
                                        "depth":{"type":"integer","minimum":1,"maximum":4}},"required":["symbol_id"],"additionalProperties":False}},
    {"name":"guardian_get_context", "description":"Read small source snippets backed by file fingerprints; fails closed for stale snapshots. Source is sent only to requesting agent.",
     "inputSchema":{"type":"object","properties":{"query":{"type":"string","minLength":1,"maxLength":200},
                                        "max_chars":{"type":"integer","minimum":256,"maximum":32000}},"required":["query"],"additionalProperties":False}},
    {"name":"guardian_tree","description":"Offline, bounded tree of recognized indexed source files; helps navigate complex folders without reading code.","inputSchema":{"type":"object","properties":{"depth":{"type":"integer","minimum":1,"maximum":20},"limit":{"type":"integer","minimum":1,"maximum":1000}},"additionalProperties":False}},
    {"name":"guardian_outline","description":"List structural definitions and line spans of one large indexed source file, without source bodies.","inputSchema":{"type":"object","properties":{"file":{"type":"string","minLength":1,"maxLength":4096},"limit":{"type":"integer","minimum":1,"maximum":300}},"required":["file"],"additionalProperties":False}},
    {"name":"guardian_hotspots","description":"Find large functions/files using local structural heuristics; does NOT claim poor code quality.","inputSchema":{"type":"object","properties":{"min_lines":{"type":"integer","minimum":1,"maximum":100000},"min_function_lines":{"type":"integer","minimum":1,"maximum":100000},"limit":{"type":"integer","minimum":1,"maximum":100}},"additionalProperties":False}},
    {"name":"guardian_repo_map","description":"Compact local symbol map with PageRank-inspired and diverse ranking. No AI/network and no source bodies.","inputSchema":{"type":"object","properties":{"focus":{"type":"string","maxLength":200},"max_chars":{"type":"integer","minimum":256,"maximum":32000},"limit":{"type":"integer","minimum":1,"maximum":500}},"additionalProperties":False}},
    {"name":"guardian_snapshot_diff","description":"Compare versioned source snapshots without Git using exact file fingerprints and structural symbols; not a semantic diff.","inputSchema":{"type":"object","properties":{"base":{"type":"string","maxLength":100},"head":{"type":"string","maxLength":100},"limit":{"type":"integer","minimum":1,"maximum":1000}},"additionalProperties":False}},
    {"name":"guardian_offline_brief","description":"Generate read-only local Markdown codebase summary and navigation map; does not write to project.","inputSchema":{"type":"object","properties":{"focus":{"type":"string","maxLength":200},"max_chars":{"type":"integer","minimum":256,"maximum":32000}},"additionalProperties":False}},
    {"name":"guardian_support_log", "description":"Export sanitized JSONL performance/quality diagnostics ZIP with NO source, prompt text or paths. Return local ZIP location.",
     "inputSchema":{"type":"object","properties":{},"additionalProperties":False}},
]
for t in TOOL_LIST:
    t["annotations"]={"readOnlyHint":t["name"] not in {"guardian_scan","guardian_support_log"},
                      "destructiveHint":False,"idempotentHint":True,"openWorldHint":False}


class GuardianMCP:
    def __init__(self, service: GuardianService):
        self.service=service
        self.handlers={
            "guardian_scan":lambda args:self.service.scan(),
            "guardian_index_status":lambda args:self.service.status(),
            "guardian_overview":lambda args:self.service.overview(),
            "guardian_find_symbol":lambda args:self.service.find_symbol(args["query"],args.get("limit",20)),
            "guardian_get_callers":lambda args:self.service.relations(args["symbol_id"],"reverse",args.get("depth",2)),
            "guardian_get_callees":lambda args:self.service.relations(args["symbol_id"],"forward",args.get("depth",2)),
            "guardian_get_context":lambda args:self.service.context(args["query"],args.get("max_chars",12000)),
            "guardian_tree":lambda args:self.service.tree(args.get("depth",5),args.get("limit",200)),
            "guardian_outline":lambda args:self.service.outline(args["file"],args.get("limit",120)),
            "guardian_hotspots":lambda args:self.service.hotspots(args.get("min_lines",300),args.get("min_function_lines",80),args.get("limit",30)),
            "guardian_repo_map":lambda args:self.service.repo_map(args.get("focus",""),args.get("max_chars",6000),args.get("limit",80)),
            "guardian_snapshot_diff":lambda args:self.service.diff(args.get("base"),args.get("head"),args.get("limit",100)),
            "guardian_offline_brief":lambda args:self.service.brief(args.get("focus",""),args.get("max_chars",6000)),
            "guardian_support_log":lambda args:self.service.support_log(),
        }

    @staticmethod
    def response(id_:Any, result:Any=None, error:dict|None=None) -> dict:
        item={"jsonrpc":"2.0","id":id_}
        if error is None: item["result"]=result
        else:item["error"]=error
        return item

    def dispatch(self,msg:dict) -> dict|None:
        if not isinstance(msg,dict) or msg.get("jsonrpc")!="2.0":
            return self.response(msg.get("id") if isinstance(msg,dict) else None,
                                 error={"code":-32600,"message":"Invalid JSON-RPC request"})
        method=msg.get("method")
        req_id=msg.get("id")
        if req_id is None:  # initialized, cancelled and other notifications
            return None
        if method=="initialize":
            p=msg.get("params") or {}
            ver=p.get("protocolVersion") or "2025-03-26"
            # Server advertises the requested known version for compatibility.
            if ver not in {"2025-03-26","2025-06-18","2024-11-05"}:
                ver="2025-03-26"
            return self.response(req_id,{"protocolVersion":ver,
                          "capabilities":{"tools":{"listChanged":False}},
                          "serverInfo":{"name":"engineering-guardian","version":__version__},
                          "instructions":"Local read-only code intelligence; run guardian_scan first. Candidate CALLS edges are not exact semantics. Refuse stale snapshots."})
        if method=="ping":
            return self.response(req_id,{})
        if method=="tools/list":
            return self.response(req_id,{"tools":TOOL_LIST})
        if method=="tools/call":
            params=msg.get("params") or {}
            name=params.get("name")
            args=params.get("arguments") or {}
            if name not in self.handlers:
                return self.response(req_id,error={"code":-32602,"message":"Unknown MCP tool"})
            tool=next(t for t in TOOL_LIST if t["name"]==name)
            try:
                if not isinstance(args,dict) or any(k not in tool["inputSchema"]["properties"] for k in args):
                    raise ValueError("Unrecognized tool parameters")
                for required in tool["inputSchema"].get("required",[]):
                    if not isinstance(args.get(required),str) or not args[required].strip():
                        raise ValueError("Required parameter missing")
                for k,v in args.items():
                    spec=tool["inputSchema"]["properties"][k]
                    if spec["type"]=="integer" and (type(v) is not int or not spec["minimum"]<=v<=spec["maximum"]):
                        raise ValueError("Numeric parameter out of range")
                    if spec["type"]=="string" and (not isinstance(v,str) or len(v)>spec["maxLength"]):
                        raise ValueError("String parameter out of range")
                result=self.handlers[name](args)
                payload=json.dumps(result,ensure_ascii=False,separators=(",",":"),default=str)
                # Bound tool response size even when graph contains thousands of edges.
                if len(payload)>160_000:
                    result={"truncated":True,"reason":"Tool response limit exceeded; narrow your query","result_type":name}
                    payload=json.dumps(result)
                return self.response(req_id,{"content":[{"type":"text","text":payload}],"isError":False})
            except Exception as exc:
                self.service.metrics.error("tool_call",exc,tool_name=name)
                # Exception messages sometimes contain paths; do not echo them.
                codes={"StaleSnapshotError":"INDEX_STALE", "SourceChangedDuringScan":"SOURCE_CHANGED",
                       "KeyError":"NOT_FOUND","RuntimeError":"INDEX_MISSING",
                       "ValueError":"INVALID_ARGUMENT","PermissionError":"PERMISSION_DENIED"}
                code=codes.get(type(exc).__name__,"TOOL_FAILED")
                return self.response(req_id,{"content":[{"type":"text","text":json.dumps({
                    "error":code,"exception_type":type(exc).__name__,
                    "action":"Run guardian_index_status and guardian_scan, then retry; use support_log if persistent"})}],"isError":True})
        return self.response(req_id,error={"code":-32601,"message":"Method not found"})


def main() -> None:
    # MCP stdio is UTF-8 JSON-RPC, independent of a host OS's code page.
    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="strict")
    p=argparse.ArgumentParser(prog="guardian-mcp",description="Read-only Engineering Guardian stdio MCP server")
    p.add_argument("--root",required=True,help="Single authorized local source folder; cannot be changed by MCP tools")
    p.add_argument("--db",default=None,help="Optional SQLite cache location")
    args=p.parse_args()
    server=GuardianMCP(GuardianService(args.root,args.db))
    for line in sys.stdin:
        if not line.strip(): continue
        try:
            message=json.loads(line)
            result=server.dispatch(message)
        except (ValueError,TypeError,json.JSONDecodeError):
            result=server.response(None,error={"code":-32700,"message":"Parse error"})
        if result is not None:
            sys.stdout.write(json.dumps(result,ensure_ascii=False,separators=(",",":"))+"\n")
            sys.stdout.flush()


if __name__=="__main__":
    main()
