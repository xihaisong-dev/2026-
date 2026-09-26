# PDF 空白页与版面诊断

- PDF: `C:/Users/Lenovo/.codex/worktrees/q1-two-methods-word/2026华为杯数学建模/论文/数模论文.pdf`
- 页数: 103
- 关键问题: 0
- 预期例外: 3

| 页码 | 状态 | 正文行占用 | 最大空白带 | 底部空白 | 原因 |
|---:|---|---:|---:|---:|---|
| 1 | expected_exception | 37.1% | 31.1% | 31.1% | low_body_row_occupancy; exception=cover_or_first_page |
| 39 | expected_exception | 26.4% | 64.2% | 64.2% | low_body_row_occupancy, large_contiguous_blank_band, large_trailing_whitespace; exception=bibliography_start |
| 103 | expected_exception | 38.5% | 50.9% | 50.9% | low_body_row_occupancy, large_contiguous_blank_band, large_trailing_whitespace; exception=terminal_page |
