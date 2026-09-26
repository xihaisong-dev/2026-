# PDF 空白页与版面诊断

- PDF: `C:/Users/Lenovo/.codex/worktrees/q123-manuscript/论文/数模论文.pdf`
- 页数: 98
- 关键问题: 0
- 预期例外: 2

| 页码 | 状态 | 正文行占用 | 最大空白带 | 底部空白 | 原因 |
|---:|---|---:|---:|---:|---|
| 1 | expected_exception | 37.1% | 31.1% | 31.1% | low_body_row_occupancy; exception=cover_or_first_page |
| 98 | expected_exception | 19.5% | 73.8% | 73.8% | low_body_row_occupancy, large_contiguous_blank_band, large_trailing_whitespace; exception=terminal_page |
