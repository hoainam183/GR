---
mode: agent
description: Implement a RAG v2 task from rag_v2_phase_tasks.md following project conventions
tools:
  - read_file
  - file_search
  - grep_search
  - create_file
  - replace_string_in_file
  - multi_replace_string_in_file
  - run_in_terminal
  - get_errors
  - manage_todo_list
---

# Implement RAG v2 Task

Implement task **${{ input:task_id: Task ID từ rag_v2_phase_tasks.md, ví dụ: 1.1, 2.1, 3.2 }}** trong hệ thống RAG v2.

## Bước 1 — Đọc spec và context

1. Đọc `src/RAG_v2/rag_v2_phase_tasks.md` và `src/RAG_v2/development_guide.md` để lấy chi tiết task.
2. Đọc `__init__.py` của module liên quan (nếu có).
3. Đọc 1–2 file đã implement trong cùng layer (ví dụ: `embedding/bge_m3.py` nếu implement embedding) để hiểu pattern.

## Bước 2 — Lập kế hoạch

Dùng `manage_todo_list` để tạo danh sách các file cần tạo/sửa trước khi bắt đầu code.

## Bước 3 — Implement theo conventions

Áp dụng **toàn bộ** conventions sau — không được bỏ sót:

### Python file structure
```python
"""<Tên class/module> — <mục đích một dòng>."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, ...

# --- project imports ---
from <module> import <Base>

logger = logging.getLogger(__name__)

# ─── Constants (nếu có) ────────────────────────────────────────────────────────
CONSTANT_NAME = value

# ═══════════════════════════════════════════════════════════════════════════════
class ClassName(Base):
    """Docstring tiếng Anh — mô tả class.

    Parameters:
        param_name: mô tả.
    """

    def __init__(self, param: type = default) -> None:
        ...

    # ------------------------------------------------------------------
    # <Tên nhóm method>
    # ------------------------------------------------------------------

    def method(self, ...) -> ...:
        """Docstring ngắn gọn."""
        ...
```

### Checklist bắt buộc cho mỗi file
- [ ] `from __future__ import annotations` ở dòng đầu tiên sau docstring
- [ ] `logger = logging.getLogger(__name__)` ở module level
- [ ] Type hints đầy đủ cho tất cả method signatures (`-> None`, `-> List[...]`)
- [ ] Return type annotation không được thiếu
- [ ] Constants viết HOA, đặt ở module level trước class
- [ ] Docstring class dùng section `Parameters:` (Google style)
- [ ] Section separators `# ------------------------------------------------------------------` cho nhóm method
- [ ] `__init__.py` export class chính sau khi tạo file mới

### Naming conventions
| Loại | Convention | Ví dụ |
|------|-----------|-------|
| Class | PascalCase | `BGEm3Embedder`, `QdrantStore` |
| Method | snake_case | `embed_query`, `index_documents` |
| Private method | `_snake_case` | `_ensure_collection`, `_encode_dense` |
| Constant | UPPER_SNAKE | `DEFAULT_COLLECTION`, `VECTOR_CONFIGS` |
| Module file | snake_case | `bge_m3.py`, `qdrant_store.py` |

### Dependency injection pattern
- Constructor nhận config params (host, port, model_name...) với defaults rõ ràng
- Không hard-code giá trị, dùng constants hoặc params
- Lazy loading cho heavy resources (models) — load trong `__init__`

## Bước 4 — Validation

1. Chạy `get_errors` trên file vừa tạo để check type errors.
2. Nếu có test file (`test_<module>.py`), chạy để verify basic functionality.
3. Kiểm tra `__init__.py` đã export đúng chưa.

## Bước 5 — Đánh dấu hoàn thành

Cập nhật `src/RAG_v2/rag_v2_phase_tasks.md`: thay `- [ ]` bằng `- [x]` cho các sub-task đã implement.

---

## Quy tắc không phá vỡ

- **Không tạo thêm file** ngoài những file được spec yêu cầu.
- **Không refactor** code trong các module khác khi chỉ được yêu cầu implement một task.
- **Không thêm** error handling cho edge cases không có trong spec — chỉ validate tại system boundaries (user input, external API).
- **Không thêm** docstring/comment vào code không thay đổi.
- Nếu task cần external service (Qdrant, ES, MongoDB), implement interface trước, không block vì service chưa chạy.
