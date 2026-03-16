---
mode: agent
description: Chuyển tham số CLI (argparse) sang config dict trong code — không cần truyền tham số qua command line
argument-hint: Đường dẫn file Python có argparse cần chuyển
tools:
  - read_file
  - grep_search
  - replace_string_in_file
  - multi_replace_string_in_file
  - get_errors
  - run_in_terminal
---

# Chuyển argparse sang In-Code Config

Chuyển **toàn bộ tham số CLI** trong file `${{ input:file: Đường dẫn file cần chuyển, ví dụ: src/train.py }}` sang một **`CONFIG` dict** ở đầu file, bỏ hoàn toàn `argparse`.

## Quy tắc

1. **Đọc file trước** — Đọc toàn bộ nội dung file nguồn trước khi làm bất cứ điều gì.
2. **Thu thập tất cả tham số** — Tìm mọi `parser.add_argument(...)` và ghi lại:
   - Tên tham số (chuẩn hoá `--foo-bar` → `foo_bar`)
   - Kiểu dữ liệu (`type=int`, `nargs="+"`, `action="store_true"`, …)
   - Giá trị mặc định (`default=...`)
3. **Tạo `CONFIG` dict** ngay sau phần `import` cuối cùng — giá trị phải lấy từ `default=` thực tế trong file, không được đặt tuỳ tiện:

   ```python
   # ---------------------------------------------------------------------------
   # Config — chỉnh tham số tại đây, không dùng CLI
   # ---------------------------------------------------------------------------
   CONFIG = {
       "param_a":   <default_từ_file>,   # <mô tả nếu cần>
       "param_b":   <default_từ_file>,
       # ... các tham số khác theo thứ tự xuất hiện trong add_argument
   }
   ```

4. **Xoá `argparse`** — Xoá toàn bộ hàm chứa `ArgumentParser` và lệnh `import argparse`. Xoá cả dòng `args = parser.parse_args()` trong `main()` hoặc khối `if __name__ == "__main__"`.
5. **Thay `args.xxx`** → `CONFIG["xxx"]` (dùng `CONFIG.get("xxx")` nếu key có thể vắng mặt) trong `main()` và mọi nơi khác trong file.
6. **Giữ nguyên logic** — Không thay đổi bất kỳ logic nào khác.
7. **Kiểm tra lỗi tĩnh** — Chạy `get_errors` trên file sau khi sửa; sửa mọi lỗi trước khi tiếp tục.
8. **Chạy thử** — Chạy file bằng terminal (background) với `.venv`:
   ```powershell
   D:\GR\.venv\Scripts\python.exe <file> --help 2>&1 | Select-Object -First 5
   ```
   Nếu file không có `--help`, thử `python <file>` và kiểm tra không có `ImportError` / `NameError`.

## Lưu ý về kiểu

| `add_argument` pattern | Kiểu Python trong CONFIG |
|---|---|
| `type=int` | `int` |
| `nargs="+"` với `default=None` | `None` |
| `nargs="+"` với `default=[...]` | `list` |
| `action="store_true"` | `bool` (`False`) |
| `type=float` | `float` |
| không có `type`, không có `default` | `None` |
| không có `type`, có `default="..."` | `str` |
