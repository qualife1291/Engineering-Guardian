# Ví dụ sử dụng thực tế (Git / không Git / Claude Code)

## 1) Quét một folder local KHÔNG có Git

```bash
python3 -m ucg.cli --root '/path/to/static-source' scan
python3 -m ucg.cli --root '/path/to/static-source' overview
python3 -m ucg.cli --root '/path/to/static-source' search renderVideo
```

## 2) Quét app Flutter có Dart + Kotlin

```bash
python3 -m ucg.cli --root '/path/to/workspace/sample-app' scan
python3 -m ucg.cli --root '/path/to/workspace/sample-app' search processOrder
```

Dùng kết quả `symbol_id` để tra `callers` hoặc `callees`. Quan hệ liên ngôn ngữ hiện **chưa giải quyết chính xác**, cần đối chiếu code gốc.

## 3) Tái sử dụng cache khi code chưa đổi

```bash
python3 -m ucg.cli --root '/path/to/project' scan
python3 -m ucg.cli --root '/path/to/project' scan
```

Lần thứ hai có `cache_hit: true`, `parsed_files: 0` nếu tập file không thay đổi.

## 4) Sau khi AI sửa source

```bash
python3 -m ucg.cli --root '/path/to/project' status
python3 -m ucg.cli --root '/path/to/project' scan
```

Dữ liệu stale sẽ bị từ chối trước khi trả context. Scan mới tái sử dụng file còn nguyên và cập nhật file đổi.

## 5) Tạo context để đưa vào ChatGPT

```bash
python3 -m ucg.cli --root '/path/to/project' context renderVideo --max-chars 6000
```

Kết quả JSON có source snippets. Chỉ đưa phần code bạn được phép chia sẻ cho model, vì context có thể chứa source proprietary.

## 6) Claude Code MCP — không copy/paste context

```bash
bash scripts/connect_claude.sh '/absolute/path/to/project'
cd '/absolute/path/to/project'
claude
```

Trong Claude chạy `/mcp`. Sau đó yêu cầu Claude dùng `guardian_scan`, `guardian_overview`, `guardian_find_symbol`, `guardian_get_callers` và `guardian_get_context` theo nhu cầu.

## 7) Xuất log để nhờ chẩn đoán hiệu năng

```bash
python3 -m ucg.cli --root '/path/to/project' support-bundle
```

Gửi ZIP support đã xem xét cùng mô tả lỗi/hoạt động mong muốn. **Đừng gửi SQLite index hoặc source project nhạy cảm.**

## 8) Không có AI, chỉ cần Terminal

```bash
python3 -m ucg.cli --root '/path/to/sample-app' tree --depth 4
python3 -m ucg.cli --root '/path/to/sample-app' outline src/example.py
python3 -m ucg.cli --root '/path/to/sample-app' hotspots --min-lines 300
python3 -m ucg.cli --root '/path/to/sample-app' repo-map --focus processOrder --text
python3 -m ucg.cli --root '/path/to/sample-app' brief --format markdown > codebase-brief.md
python3 -m ucg.cli --root '/path/to/sample-app' diff
```

Không cần Git, API key hay model. `diff` chỉ so sánh các snapshot đã scan và không chứng minh tương đương logic. Xem [OFFLINE_INTELLIGENCE.md](OFFLINE_INTELLIGENCE.md).
