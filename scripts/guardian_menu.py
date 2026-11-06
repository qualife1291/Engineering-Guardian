from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ucg.engine import scan_workspace
from ucg.service import GuardianService
from ucg.context import StaleSnapshotError
from ucg.diagnostics import diagnostic_summary
from ucg.store import UCGStore
from ucg.context import build_context_pack


def data_home() -> Path:
    configured = os.environ.get("GUARDIAN_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".engineering-guardian"
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def registry_path() -> Path:
    return data_home() / "workspaces.json"


def load_registry() -> dict:
    path = registry_path()
    if not path.exists():
        return {"workspaces": [], "active_workspace_id": None}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"workspaces": [], "active_workspace_id": None}


def save_registry(registry: dict) -> None:
    registry_path().write_text(json.dumps(registry, indent=2), encoding="utf-8")


def workspace_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]


def parse_user_path(value: str) -> Path | None:
    """Accept Windows drive paths, quoted paths and macOS Finder drag-and-drop.

    Avoid shlex.split() for Windows: it consumes backslashes in C:\\Users\\...
    """
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in ("'", '"'):
        candidate = candidate[1:-1]
    if os.name != "nt":
        # Finder may paste POSIX shell-escaped spaces into a Terminal prompt.
        candidate = candidate.replace(r"\ ", " ")
    return Path(candidate).expanduser().resolve()


def active_workspace(registry: dict) -> dict | None:
    wid = registry.get("active_workspace_id")
    return next((w for w in registry.get("workspaces", []) if w.get("workspace_id") == wid), None)


def choose_workspace(registry: dict) -> None:
    workspaces = registry.get("workspaces", [])
    if not workspaces:
        print("\nChưa có project nào. Hãy chọn 'Quét project mới' trước.")
        return
    print("\nCác project đã lưu:")
    for i, w in enumerate(workspaces, 1):
        marker = "  [đang chọn]" if w.get("workspace_id") == registry.get("active_workspace_id") else ""
        print(f"  {i}. {w['name']} — {w['root']}{marker}")
    raw = input("Chọn số project (Enter để hủy): ").strip()
    if not raw:
        return
    try:
        selected = workspaces[int(raw) - 1]
    except (ValueError, IndexError):
        print("Lựa chọn không hợp lệ.")
        return
    registry["active_workspace_id"] = selected["workspace_id"]
    save_registry(registry)


def scan_new_or_refresh(registry: dict, existing: dict | None = None) -> None:
    if existing:
        root = Path(existing["root"])
        print(f"\nQuét lại: {root}")
    else:
        print("\nDán đường dẫn folder source vào đây.")
        print("Mẹo: kéo-thả folder từ Finder vào cửa sổ Terminal rồi nhấn Enter.")
        root = parse_user_path(input("Folder: "))
        if root is None:
            return
    if not root.exists() or not root.is_dir():
        print(f"Không tìm thấy folder: {root}")
        return

    wid = workspace_id(root)
    db = data_home() / "indexes" / f"{wid}.sqlite"
    db.parent.mkdir(parents=True, exist_ok=True)
    print("\nĐang quét source. Không sửa bất kỳ file gốc nào...")
    try:
        result = GuardianService(str(root), str(db)).scan()
    except Exception as exc:
        print(f"\nQuét thất bại ({type(exc).__name__}). Dùng guardian doctor hoặc support-bundle để điều tra.")
        return

    item = {
        "workspace_id": wid,
        "name": root.name or str(root),
        "root": str(root),
        "db": str(db),
        "snapshot_id": result["snapshot_id"],
        "last_scan": datetime.now().isoformat(timespec="seconds"),
    }
    workspaces = [w for w in registry.get("workspaces", []) if w.get("workspace_id") != wid]
    workspaces.insert(0, item)
    registry["workspaces"] = workspaces
    registry["active_workspace_id"] = wid
    save_registry(registry)

    overview = result["overview"]
    print("\nQUÉT HOÀN TẤT")
    print(f"  Project        : {root.name}")
    print(f"  Files          : {overview['files']}")
    print(f"  Lines          : {overview['lines']:,}")
    print(f"  Symbols        : {overview['symbols']:,}")
    print(f"  Candidate edges: {overview['edges']:,}")
    print(f"  Snapshot       : {result['snapshot_id']}")
    print(f"  Thời gian      : {result['timings_seconds']['total']:.3f}s")
    print(f"  Index lưu tại  : {db}")
    if result.get("skipped_files"):
        print(f"  File bỏ qua    : {result['skipped_files']}")
    if result.get("diagnostics"):
        print(f"  Cảnh báo       : {len(result['diagnostics'])}")
    print("\nLưu ý: quan hệ CALLS hiện là candidate heuristic, chưa được compiler xác minh.")


def open_store(workspace: dict) -> UCGStore:
    return UCGStore(workspace["db"])


def show_overview(workspace: dict) -> None:
    store = open_store(workspace)
    try:
        GuardianService(workspace["root"], workspace["db"]).status()
        result = GuardianService(workspace["root"], workspace["db"]).overview()
        print(f"\nPROJECT: {workspace['name']}")
        print(f"Root: {workspace['root']}")
        print(f"Snapshot: {workspace['snapshot_id']}")
        print(f"Files: {result['files']} | Lines: {result['lines']:,} | Symbols: {result['symbols']:,} | Edges: {result['edges']:,}")
        print("Languages:")
        for lang, count in sorted(result["languages"].items()):
            print(f"  - {lang}: {count} files")
    finally:
        store.close()


def find_symbol(workspace: dict, prompt: str) -> list[dict] | None:
    query = input(prompt).strip()
    if not query:
        return None
    store = open_store(workspace)
    try:
        hits = GuardianService(workspace["root"], workspace["db"]).find_symbol(query, limit=30)["symbols"]
    finally:
        store.close()
    if not hits:
        print("Không tìm thấy symbol phù hợp.")
        return None
    print(f"\nTìm thấy {len(hits)} kết quả:")
    for i, hit in enumerate(hits, 1):
        print(f"  {i}. {hit['kind']} {hit['qualified_name']} — {hit['file_path']}:{hit['start_line']}")
    if len(hits) == 1:
        return hits
    raw = input("Chọn số kết quả (Enter để hủy): ").strip()
    if not raw:
        return None
    try:
        return [hits[int(raw) - 1]]
    except (ValueError, IndexError):
        print("Lựa chọn không hợp lệ.")
        return None


def search_symbols(workspace: dict) -> None:
    hits = find_symbol(workspace, "Nhập tên function/class/symbol: ")
    if not hits:
        return
    for hit in hits:
        print(f"\n{hit['kind'].upper()}: {hit['qualified_name']}")
        print(f"File: {hit['file_path']}:{hit['start_line']}")
        print(f"Signature: {hit['signature']}")


def trace_symbols(workspace: dict, direction: str) -> None:
    hits = find_symbol(workspace, "Nhập tên function cần truy vết: ")
    if not hits:
        return
    hit = hits[0]
    store = open_store(workspace)
    try:
        edges = GuardianService(workspace["root"], workspace["db"]).relations(hit["symbol_id"], direction, max_depth=4)["edges"]
        print(f"\n{'CALLERS' if direction == 'reverse' else 'CALLEES'} của {hit['qualified_name']}:")
        if not edges:
            print("Không tìm thấy quan hệ trong graph hiện tại.")
            return
        for edge in edges[:100]:
            row = store.conn.execute(
                "SELECT name, qualified_name, file_path, start_line FROM symbols WHERE snapshot_id=? AND symbol_id=?",
                (workspace["snapshot_id"], edge["to"]),
            ).fetchone()
            if row:
                print(f"  depth {edge['depth']}: {row[1]} — {row[2]}:{row[3]} [{edge['resolution']}]")
        if len(edges) > 100:
            print(f"  ... còn {len(edges) - 100} edges")
    finally:
        store.close()


def create_context(workspace: dict) -> None:
    query = input("Bạn muốn AI hiểu function/module nào? Nhập tên hoặc từ khóa: ").strip()
    if not query:
        return
    result = GuardianService(workspace["root"], workspace["db"]).context(query, max_chars=32_000)
    out_dir = data_home() / "contexts"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = out_dir / f"context-{stamp}.md"
    lines = [
        f"# Engineering Guardian Context: {query}", "",
        f"- Project: {workspace['name']}",
        f"- Snapshot: {workspace['snapshot_id']}",
        f"- Symbols: {len(result['symbols'])}",
        f"- Estimated tokens (characters / 4): {result['estimated_tokens_char_div_4']}",
        f"- Truncated: {result['truncated']}", "",
        "> POC note: source relationships are heuristic candidates unless verified by a semantic adapter.", "",
    ]
    for item in result["symbols"]:
        lines += [f"## {item['qualified_name']} ({item['kind']})", "",
                  f"Source: `{item['file_path']}:{item['start_line']}`", "", "```",
                  item["snippet"], "```", ""]
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nContext pack đã tạo: {output}")
    print(f"Symbols: {len(result['symbols'])} | Ước lượng: {result['estimated_tokens_char_div_4']} tokens")
    print("Mở file Markdown này và gửi cho ChatGPT/Codex để phân tích tiếp.")


def run_tests() -> None:
    print("\nĐang chạy self-check...")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], cwd=ROOT
    )
    print("\nSELF-CHECK: PASS" if result.returncode == 0 else "\nSELF-CHECK: FAILED")



def offline_menu_action(workspace: dict, choice: str) -> None:
    """Navigate the index without calling an AI model or modifying app source."""
    service = GuardianService(workspace["root"], workspace["db"])
    try:
        if choice == "12":
            value = service.tree(depth=4, limit=200)
            for entry in value["entries"]:
                marker = "/" if entry["kind"] == "directory" else ""
                print("  " * entry["depth"] + entry["path"].split("/")[-1] + marker)
            if value["truncated"]:
                print("... limited output; use CLI tree --limit for more.")
        elif choice == "13":
            relative = input("Đường dẫn file trong project (ví dụ src/main.py): ").strip()
            value = service.outline(relative)
            print(f"\n{value['file_path']} ({value['lines']} lines)")
            for symbol in value["symbols"]:
                print(f"  {symbol['line']}-{symbol['end_line']}: {symbol['kind']} {symbol['name']}")
            if value["truncated"]:
                print("... more symbols; use CLI outline --limit.")
        elif choice == "14":
            value = service.hotspots(min_lines=300, min_function_lines=80, limit=30)
            print("\nFILES TO INSPECT (size/structure signals, NOT defects):")
            for item in value["items"]:
                print(f"  {item['lines']} lines | {item['file_path']} | {', '.join(item['signals'])}")
        elif choice == "15":
            focus = input("Từ khóa/mục tiêu (Enter: tổng quan): ").strip()
            value = service.repo_map(focus=focus, max_chars=6000, limit=80)
            print("\n" + value["text"])
            if value["truncated"]:
                print("... map truncated to keep it short.")
        elif choice == "16":
            value = service.diff()
            print("\nSNAPSHOT DIFF (file changes are exact; symbol changes are structural):")
            print(json.dumps(value, ensure_ascii=False, indent=2))
        elif choice == "17":
            focus = input("Chủ đề cần tóm tắt (Enter: toàn dự án): ").strip()
            value = service.brief(focus=focus, max_chars=6000)
            target_dir = data_home() / "reports"
            target_dir.mkdir(parents=True, exist_ok=True)
            filename = "offline-brief-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".md"
            target = target_dir / filename
            target.write_text(value["markdown"], encoding="utf-8")
            print("\nĐã lưu báo cáo local:", target)
            print("Không dùng AI và không sửa source project.")
    except Exception as exc:
        # Never print exception text: it may embed confidential paths.
        print("\nKhông thực hiện được:", type(exc).__name__)
        print("Kiểm tra index bằng menu 3 hoặc quét lại bằng menu 2.")

def main() -> None:
    registry = load_registry()
    while True:
        current = active_workspace(registry)
        print("\n" + "=" * 58)
        print(" ENGINEERING GUARDIAN — LOCAL CODE INTELLIGENCE")
        print("=" * 58)
        print(f"Project đang chọn: {current['name']}" if current else "Chưa chọn project")
        print("\n  1. Quét project folder mới")
        print("  2. Quét lại project đang chọn")
        print("  3. Xem tổng quan project")
        print("  4. Tìm function / class / symbol")
        print("  5. Tìm nơi gọi function (callers)")
        print("  6. Tìm function được gọi (callees)")
        print("  7. Tạo context pack gửi cho AI")
        print("  8. Chuyển project đã lưu")
        print("  9. Tự kiểm tra (self-check)")
        print(" 10. Xem thống kê tốc độ/chất lượng (log summary)")
        print(" 11. Xuất ZIP chẩn đoán để gửi nâng cấp")
        print(" 12. Xem cây folder source (offline)")
        print(" 13. Xem outline file dài (offline)")
        print(" 14. Tìm file/function cần review (offline)")
        print(" 15. Repo map: đọc code đúng trọng tâm (offline)")
        print(" 16. Xem thay đổi giữa 2 lần quét (không cần Git)")
        print(" 17. Xuất Markdown Codebase Brief (không cần AI)")
        print("  0. Thoát")
        choice = input("\nChọn chức năng: ").strip()
        if choice == "0":
            print("Đã thoát Engineering Guardian.")
            break
        if choice == "1":
            scan_new_or_refresh(registry)
            registry = load_registry()
            continue
        if choice == "8":
            choose_workspace(registry)
            registry = load_registry()
            continue
        if choice == "9":
            run_tests()
            continue
        if not current:
            print("Hãy quét project trước.")
            continue
        if choice == "2":
            scan_new_or_refresh(registry, current)
            registry = load_registry()
        elif choice == "3":
            show_overview(current)
        elif choice == "4":
            search_symbols(current)
        elif choice == "5":
            trace_symbols(current, "reverse")
        elif choice == "6":
            trace_symbols(current, "forward")
        elif choice == "7":
            create_context(current)
        elif choice in {"12","13","14","15","16","17"}:
            offline_menu_action(current, choice)
        elif choice == "10":
            report = diagnostic_summary(current["root"])
            print("\nTHỐNG KÊ CHẤT LƯỢNG/VẬN HÀNH (không phải semantic accuracy)")
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif choice == "11":
            report = GuardianService(current["root"], current["db"]).support_log()
            print("\nĐã tạo ZIP đã lọc thông tin:", report["bundle_path"])
            print("Hãy kiểm tra nội dung ZIP trước khi gửi. Không gửi SQLite index/source riêng tư.")
        else:
            print("Lựa chọn không hợp lệ.")


if __name__ == "__main__":
    main()
