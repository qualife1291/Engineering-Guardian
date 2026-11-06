#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo ""
echo "=========================================================="
echo "       ENGINEERING GUARDIAN — EASY START"
echo "=========================================================="
echo ""
PYTHON_BIN=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v "$candidate")"
      break
    fi
  fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  echo "Không tìm thấy Python 3.11 trở lên."
  echo "Cài Python tại: https://www.python.org/downloads/macos/"
  if command -v open >/dev/null 2>&1; then
    read -r -p "Nhấn Enter để mở trang tải Python (hoặc Ctrl+C để hủy)..."
    open "https://www.python.org/downloads/macos/"
  fi
  exit 1
fi

echo "Python: $("$PYTHON_BIN" --version)"
VENV="$ROOT/.venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Lần đầu chạy: đang tạo môi trường riêng..."
  "$PYTHON_BIN" -m venv "$VENV"
fi
GUARDIAN_PY="$VENV/bin/python"
"$GUARDIAN_PY" -m compileall -q "$ROOT/ucg" "$ROOT/scripts"
echo ""
echo "Mở Engineering Guardian..."
echo "Index mặc định lưu tại: ~/.engineering-guardian"
echo "Có thể đổi bằng biến môi trường GUARDIAN_HOME."
echo ""
exec "$GUARDIAN_PY" "$ROOT/scripts/guardian_menu.py"
