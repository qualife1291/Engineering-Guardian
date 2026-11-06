# Documentation index — mở đúng tài liệu, không đọc tất cả

| Đối tượng / tình huống | Tài liệu | Nội dung |
|---|---|---|
| **AI coding agent (đọc đầu tiên)** | [AGENTS.md](../AGENTS.md) | Quy tắc và entry points, ngắn gọn |
| Phát triển hoặc debug code Guardian | [PROJECT_MAP.md](PROJECT_MAP.md) | Module → file cần mở |
| Developer mới | [README.md](../README.md) | Khả năng, giới hạn, lệnh cơ bản |
| **Windows native / WSL2** | [WINDOWS_SETUP_VI.md](WINDOWS_SETUP_VI.md) | Setup, .cmd/.ps1, MCP, cache, troubleshoot |
| macOS | [EASY_START_VI.md](EASY_START_VI.md) | App launcher, menu, CLI |
| Claude Code MCP | [CLAUDE_CODE.md](CLAUDE_CODE.md) | Kết nối AI và prompt mẫu |
| Công thức CLI | [USAGE_EXAMPLES_VI.md](USAGE_EXAMPLES_VI.md) | Scan/search/callers/context |
| Thực thi và đóng góp | [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Thêm tính năng, kiểm thử, review |
| Thiết kế | [ARCHITECTURE.md](ARCHITECTURE.md) | Source-to-index pipeline |
| Test và nghiệm thu | [TESTING.md](TESTING.md), [ACCEPTANCE.md](ACCEPTANCE.md) | Kết quả và giới hạn |
| Benchmark | [BENCHMARK.md](BENCHMARK.md), [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) | Quy trình và số đo |
| Công cụ nền tảng | [EXISTING_TOOLS_COMPARISON.md](EXISTING_TOOLS_COMPARISON.md) | So sánh grep/Jedi/TypeScript LS |
| **Offline algorithms & no-AI usage** | [OFFLINE_INTELLIGENCE.md](OFFLINE_INTELLIGENCE.md), [MULTI_AGENT.md](MULTI_AGENT.md) | PageRank, diversity, CLI and agents |
| **Tree-sitter & Change X-Ray** | [TREE_SITTER_CHANGE_XRAY.md](TREE_SITTER_CHANGE_XRAY.md) | Grammar setup, resolution levels, impact analysis |
| **Privacy for public distribution** | [PRIVACY.md](PRIVACY.md) | Generic examples, code/log sharing and history warning |
| **Gửi log lỗi / hiệu năng** | [DIAGNOSTICS.md](DIAGNOSTICS.md) | Diagnostic ZIP đã lọc |
| Bảo mật và giới hạn quyền | [SECURITY.md](../SECURITY.md) | Trust boundary |
| Version và phát hành | [CHANGELOG.md](../CHANGELOG.md), [RELEASING.md](RELEASING.md) | Changelog + release process |

**Cần nhớ:** v0.5.0 là POC Python offline-first với Tree-sitter tùy chọn; chưa có SCIP hoặc phân tích runtime. Candidate edges không phải dependencies đã được xác minh. Đừng suy diễn tính chính xác của graph từ tốc độ benchmark.
