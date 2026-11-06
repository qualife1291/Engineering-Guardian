# Cài đặt và sử dụng Engineering Guardian (macOS)

> Windows 10/11: dùng [hướng dẫn Windows / PowerShell / WSL2](WINDOWS_SETUP_VI.md), không chạy file `.command` trên Windows.

## Yêu cầu

- macOS Intel hoặc Apple Silicon (M1/M2/M3/M4).
- Python 3.11 trở lên.
- Không cần Git, Rust, Node.js, Docker, LLM hoặc API key cho POC hiện tại.
- Core POC dùng Python standard library, không cần tải thư viện Python bên ngoài.

## Cài đặt lần đầu

1. Tải ZIP `engineering-guardian-easy-start.zip`.
2. Giải nén vào nơi muốn lưu, ví dụ `/path/to/EngineeringGuardian`.
3. Mở folder vừa giải nén.
4. Nhấn đúp `Start Engineering Guardian.command`.
5. Nếu macOS chặn file, nhấn chuột phải → **Open** → **Open**.
6. Terminal tự tạo môi trường Python riêng `.venv`, kiểm tra source và mở menu.

Nếu máy chưa có Python 3.11+, launcher sẽ hướng dẫn mở trang tải Python chính thức. Launcher không tự cài Homebrew hoặc thay đổi Python hệ thống.

## Sử dụng

1. Chọn `1. Quét project folder mới`.
2. Kéo-thả folder source từ Finder vào cửa sổ Terminal, nhấn Enter.
3. Đợi scan hoàn tất.
4. Dùng menu:
   - `3`: xem tổng quan project.
   - `4`: tìm function/class/symbol.
   - `5`: tìm nơi gọi function (callers).
   - `6`: tìm function mà function hiện tại gọi (callees).
   - `7`: tạo context pack Markdown để gửi cho ChatGPT/Codex.
   - `2`: quét lại sau khi source thay đổi.
   - `8`: chuyển project đã lưu.
   - `9`: chạy self-check.
   - `10`: xem thống kê tốc độ/chất lượng theo log.
   - `11`: xuất ZIP support để gửi kiểm tra và nâng cấp.
   - `0`: thoát.

## Dữ liệu được lưu ở đâu?

Mặc định: `~/.engineering-guardian/`

- `indexes/`: SQLite index riêng theo từng workspace.
- `contexts/`: context pack Markdown đã xuất.
- `workspaces.json`: danh sách project đã thêm.

Có thể đặt dữ liệu trên SSD ngoài bằng cách mở Terminal và chạy:

```bash
export GUARDIAN_HOME="/path/to/EngineeringGuardianData"
```

Sau đó khởi chạy file `Start Engineering Guardian.command` từ cùng cửa sổ Terminal.

## Chạy bằng Terminal

```bash
cd "/path/to/engineering-guardian"
chmod +x "Start Engineering Guardian.command"
./"Start Engineering Guardian.command"
```

## Gỡ cài đặt

1. Thoát Engineering Guardian.
2. Xóa folder source `engineering-guardian`.
3. Xóa `~/.engineering-guardian` nếu muốn xóa cả index và context pack.
4. Xóa folder `.venv` trong source nếu chỉ muốn xóa môi trường cài đặt.

## Giới hạn của POC

- Đây là POC có menu Terminal, chưa phải ứng dụng GUI.
- Python dùng AST; các ngôn ngữ còn lại vẫn dùng parser heuristic, chưa tích hợp Tree-sitter/SCIP/LSP.
- Quan hệ CALLS là candidate heuristic, không phải kết luận compiler-verified.
- Chỉ scan file theo extension hỗ trợ; file nhị phân, file bí mật, symlink và thư mục build/cache bị bỏ qua.
- Scan không chỉnh sửa source. Index nằm ngoài source folder.
- Chưa tự theo dõi thay đổi theo thời gian thực; chọn `2. Quét lại project` sau khi code thay đổi.

## Troubleshooting

- **Python quá cũ:** cài Python 3.11+ từ https://www.python.org/downloads/macos/.
- **macOS chặn `.command`:** chuột phải → Open → Open một lần.
- **Không có quyền thực thi:** chạy `chmod +x "Start Engineering Guardian.command"` trong Terminal.
- **Folder có dấu cách:** kéo-thả folder từ Finder vào Terminal để tự điền đường dẫn.
- **Folder trên SSD ngoài:** chọn folder trực tiếp; Guardian đọc tại chỗ và không copy source.

## Dùng trực tiếp với Claude Code (không copy context)

Không cần đưa Guardian vào folder source. Đặt hai folder ngang hàng; xem [`CLAUDE_CODE.md`](CLAUDE_CODE.md). Tại folder Engineering Guardian, chạy:

```bash
bash scripts/connect_claude.sh '/đường/dẫn/đầy/đủ/đến/project'
```

Mở Claude Code trong folder dự án → `/mcp` → kiểm tra `engineering-guardian`.

## Log và nâng cấp phiên bản

- Nhật ký version: [`CHANGELOG.md`](../CHANGELOG.md) (được commit theo release).
- Log hiệu năng/chất lượng: `$GUARDIAN_HOME/diagnostics/YYYY-MM-DD/*.jsonl`.
- Trong menu chọn `10` để xem thống kê, `11` để xuất ZIP gửi hỗ trợ.
- Hoặc chạy `python3 -m ucg.cli --root PROJECT support-bundle`.
- Log không chứa code/path/prompt theo thiết kế; **xem lại ZIP trước khi gửi**.
- Chi tiết: [`DIAGNOSTICS.md`](DIAGNOSTICS.md).

## Offline-first (không cần AI)

Menu `12–17` cho phép xem file tree, outline function, hotspot, repo map, diff giữa các lần scan và tạo Markdown Brief, không cần LLM hoặc kết nối mạng. Xem [Offline Intelligence](OFFLINE_INTELLIGENCE.md).
