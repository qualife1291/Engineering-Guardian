# Engineering Guardian trên Windows (PowerShell, CMD, WSL2)

> Bản 0.3.x là POC Python và MCP stdio. Không phải ứng dụng .exe, chưa có Tree-sitter/SCIP. Tất cả quan hệ CALLS hiện là ứng viên heuristic, **không** phải bằng chứng compiler.

## 1. Chọn đúng cách cài

| Môi trường | Dùng launcher | Đường dẫn project | Lệnh kết nối Claude |
|---|---|---|---|
| **Windows 10/11 native** | `Start Engineering Guardian.cmd` | `D:\Dev\My App` | `scripts\connect_claude.ps1` |
| **PowerShell 7 trên Windows** | Cũng dùng `.cmd` hoặc `.ps1` | `D:\Dev\My App` | `scripts\connect_claude.ps1` |
| **WSL2 Ubuntu/Linux** | `Start Engineering Guardian.command` qua Bash, hoặc CLI Python | `/mnt/d/Dev/My App` | `scripts/connect_claude.sh` bên trong WSL |
| **Git Bash native** | Ưu tiên PowerShell native để tránh lẫn Python Windows/Linux | `D:\... ` | PowerShell, không dùng đường dẫn `/mnt/d` |

Windows native và WSL2 có **môi trường Python/MCP riêng**. Không trộn `.venv\Scripts\python.exe` với `.venv/bin/python`, hoặc đăng ký root `C:\...` cho Python chạy trong WSL.

## 2. Yêu cầu

- Python **3.11 trở lên**, cài từ [python.org](https://www.python.org/downloads/windows/) và kiểm tra `py -3 --version` hoặc `python --version`.
- Claude Code CLI (nếu muốn dùng AI/MCP); kiểm tra `claude --version`.
- Git for Windows **chỉ cần nếu muốn dùng `git clone`**; có thể tải ZIP từ GitHub và giải nén. Claude Code Windows native hiện có thể dùng PowerShell fallback nếu không có Git Bash.
- **Không cần** Rust, Node, Docker, API key LLM cho scanner; không cần chạy với quyền Administrator.

Cài Claude Code nếu chưa có (PowerShell):

```powershell
winget install Anthropic.ClaudeCode
```

Hoặc dùng installer chính thức theo [Claude Code setup](https://code.claude.com/docs/en/setup). Mở lại PowerShell sau khi cài.

## 3. Cách dễ nhất: mở bằng hai cú nhấp

1. Tải `Engineering-Guardian` từ [GitHub](https://github.com/qualife1291/Engineering-Guardian) → **Code → Download ZIP**, giải nén ví dụ `D:\Tools\Engineering-Guardian`.
2. Nhấp đúp `Start Engineering Guardian.cmd`.
3. Launcher tạo `.venv` bằng Python 3.11+ hiện có, không tải thư viện Python ngoài Internet.
4. Chọn `1` trong menu và nhập đường dẫn folder source **Windows native**, ví dụ `D:\Dev\AirVoice Wireless` (có thể có dấu cách).
5. Chọn `3` để xem cấu trúc, `4` để tìm symbol, `5/6` để truy vết candidate callers/callees, `10/11` để xem/xuất log.

Script `.cmd` khởi chạy PowerShell với `ExecutionPolicy Bypass` **chỉ cho tiến trình đó**, không thay đổi chính sách hệ thống hay User. Hãy xem nội dung script trước khi chạy nếu máy công ty có hạn chế.

## 4. Kết nối trực tiếp Claude Code qua MCP

Đặt Engineering Guardian bên cạnh folder ứng dụng:

```text
D:\Dev\
├── Engineering-Guardian\
└── airvoice-wireless-app\
```

Mở **PowerShell** tại folder Engineering Guardian:

```powershell
cd 'D:\Dev\Engineering-Guardian'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\connect_claude.ps1 -ProjectPath 'D:\Dev\airvoice-wireless-app'
```

Kiểm tra script in ra chính xác root và vị trí Python, trả lời `y` nếu đồng ý. Đây là MCP **local scope** chỉ có hiệu lực trong project được chọn; không cấp quyền ghi vào source cho Guardian.

Sau đó:

```powershell
cd 'D:\Dev\airvoice-wireless-app'
claude
```

Trong Claude Code nhập `/mcp`, tìm `engineering-guardian`. Prompt mẫu: “Use Guardian to scan this project, map the eSIM entry points and give evidence for candidate callers. Do not modify project files.”

Nếu muốn bỏ kết nối: từ folder ứng dụng dùng `claude mcp remove engineering-guardian -s local` (kiểm tra cú pháp trên phiên bản Claude Code bạn cài bằng `claude mcp remove --help`).

## 5. Dùng hoàn toàn bằng CLI (không cần Claude)

```powershell
cd 'D:\Dev\Engineering-Guardian'
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' scan
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' status
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' overview
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' search downloadProfile
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' log-summary
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' support-bundle
```

## 6. Đổi vị trí cache/log (ổ D: hoặc SSD ngoài)

Trước khi chạy launcher / Claude Code **trong cùng PowerShell session**:

```powershell
$env:GUARDIAN_HOME = 'D:\GuardianData'
```

Mặc định dữ liệu nằm tại `%USERPROFILE%\.engineering-guardian\`, với `indexes\` (SQLite) và `diagnostics\YYYY-MM-DD\*.jsonl`. Nếu nhấp đúp `.cmd` từ Explorer, biến môi trường chỉ đặt trong một PowerShell khác sẽ không tự áp dụng. Khi cần ổ D:, hãy chạy launcher trong cửa sổ PowerShell đã đặt biến:

```powershell
& '.\scripts\start_windows.ps1'
```

Không đặt `GUARDIAN_HOME` bên trong folder source đang quét.

## 7. Kiểm tra, nâng cấp và hỗ trợ

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' doctor
.\.venv\Scripts\python.exe -m ucg.cli --root 'D:\Dev\airvoice-wireless-app' support-bundle
```

Đọc [diagnostics](DIAGNOSTICS.md) trước khi gửi ZIP; chỉ gửi bản đã xem xét, **không gửi index SQLite hoặc source riêng tư**. Sau khi cập nhật repo bằng `git pull` hoặc giải nén bản mới, chạy lại self-check và kiểm tra MCP.

## 8. Xử lý lỗi thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `python` / `py` không tìm thấy | Cài Python 3.11+, mở PowerShell mới; kiểm tra `py -3 --version`. |
| Windows App Execution Aliases mở Microsoft Store | Dùng Python từ python.org, kiểm tra `where.exe python`, tắt alias `python.exe` nếu cần. |
| `claude` không tìm thấy | Cài Claude Code, mở terminal mới, chạy `claude --version`. |
| Execution policy chặn `.ps1` | Dùng `.cmd` hoặc `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` cho tiến trình này; kiểm tra chính sách công ty. |
| Path có dấu cách | Bao trong dấu nháy đơn `'D:\My Projects\App'`. |
| MCP không Connected | Chạy `claude mcp list` tại đúng folder ứng dụng; kiểm tra Python trong `.venv\Scripts`, thử đăng ký lại sau khi xóa registration cũ. |
| Project đổi nhưng Guardian trả kết quả cũ | Chạy `guardian_scan` hoặc CLI `scan`; xem `status`. |
| Muốn dùng WSL2 | Cài Python/Claude trong **WSL**, chạy `bash scripts/connect_claude.sh /mnt/d/Dev/airvoice-wireless-app`. Không dùng PowerShell script trong WSL. |

## 9. Bảo mật & giới hạn

Guardian **không chạy source ứng dụng**, không cấp tool sửa file hoặc chạy shell trong MCP. Nó **có thể gửi các đoạn source được yêu cầu tới mô hình Claude**, nên hãy tuân thủ chính sách dữ liệu của tổ chức. Claude Code có quyền riêng cho các công cụ khác; cấu hình Guardian không giới hạn các quyền đó. Chi tiết tại [SECURITY.md](../SECURITY.md).
