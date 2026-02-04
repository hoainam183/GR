# Data Cleaning Package for RAG System

## 📋 Tổng quan

Package này được thiết kế để làm sạch dữ liệu markdown trước khi thực hiện chunking cho hệ thống RAG (Retrieval-Augmented Generation). Nó xử lý các file markdown được convert từ PDF/HTML và loại bỏ các dữ liệu thừa, lỗi OCR, và chuẩn hóa format.

## 🏗️ Cấu trúc Project

```
src/data_cleaning/
├── __init__.py           # Package exports
├── config.py             # Cấu hình cho quá trình làm sạch
├── pipeline.py           # Pipeline xử lý tuần tự
├── utils.py              # Các hàm tiện ích
├── main.py               # CLI entry point
├── evaluate.py           # Script đánh giá chất lượng
├── cleaners/
│   ├── __init__.py       # Cleaners exports
│   ├── base.py           # Abstract base cleaner
│   ├── whitespace.py     # Xử lý khoảng trắng
│   ├── table.py          # Sửa lỗi bảng
│   ├── header_footer.py  # Xóa header/footer
│   ├── duplicate.py      # Xóa dòng lặp lại
│   ├── special_chars.py  # Chuẩn hóa ký tự
│   └── metadata.py       # Trích xuất metadata
└── README.md
```

## 🚀 Cách sử dụng

### 1. Đánh giá chất lượng trước khi làm sạch

```bash
python -m src.data_cleaning.evaluate olmocr/converted
```

### 2. Chạy pipeline làm sạch

```bash
# Cơ bản
python -m src.data_cleaning.main --input olmocr/converted --output olmocr/cleaned

# Với verbose logging
python -m src.data_cleaning.main --input olmocr/converted --output olmocr/cleaned --verbose

# Với report JSON
python -m src.data_cleaning.main --input olmocr/converted --output olmocr/cleaned --report report.json

# Xử lý một file
python -m src.data_cleaning.main --file olmocr/converted/sample.md --output sample_cleaned.md
```

### 3. Sử dụng trong code Python

```python
from src.data_cleaning import CleaningPipeline, CleaningConfig

# Tạo config tùy chỉnh
config = CleaningConfig(
    input_dir="olmocr/converted",
    output_dir="olmocr/cleaned",
    fix_ocr_errors=True,
    add_metadata_header=True
)

# Tạo pipeline và thêm default cleaners
pipeline = CleaningPipeline(config)
pipeline.add_default_cleaners()

# Xử lý tất cả files
results = pipeline.process_directory()

# Hoặc xử lý một file
result = pipeline.process_file("path/to/file.md")
```

## 🔧 Các Cleaners

| Cleaner | Chức năng |
|---------|-----------|
| `SpecialCharacterCleaner` | Chuẩn hóa Unicode, sửa lỗi OCR, xóa control chars |
| `WhitespaceCleaner` | Xóa dòng trống thừa, trailing whitespace |
| `HeaderFooterCleaner` | Xóa header/footer artifacts, số trang |
| `DuplicateLineCleaner` | Xóa dòng và đoạn văn duplicate |
| `TableCleaner` | Sửa lỗi format bảng markdown |
| `MetadataNormalizer` | Trích xuất và thêm YAML frontmatter |

## 📊 Đánh giá (Evaluation Report)

Script `evaluate.py` phân tích các file markdown và báo cáo:

- **Dòng trống thừa**: Nhiều hơn 2 dòng trống liên tiếp
- **Trailing whitespace**: Khoảng trắng cuối dòng
- **Duplicate lines**: Dòng bị lặp lại liên tiếp
- **Malformed tables**: Bảng bị lỗi format
- **OCR errors**: Các lỗi OCR đã biết (ĐHIBK -> ĐHBK, etc.)
- **Header artifacts**: Header bị lặp lại nhiều lần

**Quality Score**: 0-100, càng cao càng tốt

## ⚙️ Cấu hình

Config có thể được tùy chỉnh qua:

1. **Code trực tiếp**:
```python
config = CleaningConfig(
    max_consecutive_blank_lines=2,
    similarity_threshold=0.95,
    fix_ocr_errors=True
)
```

2. **File JSON**:
```json
{
  "input_dir": "olmocr/converted",
  "output_dir": "olmocr/cleaned",
  "fix_ocr_errors": true,
  "add_metadata_header": true
}
```

```bash
python -m src.data_cleaning.main --config config.json
```

## 📝 Output

Sau khi xử lý, mỗi file markdown sẽ có:

1. **YAML Frontmatter** với metadata:
```yaml
---
loai_van_ban: QUYẾT ĐỊNH
so_van_ban: 5445/QĐ-ĐHBK
ngay_ban_hanh: 28/05/2025
don_vi_ban_hanh: Đại học Bách khoa Hà Nội
tu_khoa: đào tạo, sinh viên, tín chỉ
---
```

2. **Nội dung đã được làm sạch**:
   - Không có dòng trống thừa
   - Bảng được format đúng
   - Lỗi OCR được sửa
   - Không có duplicate

## 🔄 Mở rộng

### Thêm Cleaner mới

```python
from src.data_cleaning.cleaners.base import BaseCleaner, CleaningResult

class CustomCleaner(BaseCleaner):
    @property
    def name(self) -> str:
        return "CustomCleaner"
    
    def clean(self, content: str) -> CleaningResult:
        result = CleaningResult(content=content)
        # Logic làm sạch ở đây
        return result
```

### Thêm OCR error mappings

```python
config = CleaningConfig(
    ocr_error_mappings={
        'sai_text': 'đúng_text',
        'lỗi_1': 'sửa_1',
    }
)
```

## 📈 Kết quả mẫu

```
SUMMARY
==================================================
Files processed: 16
Successful: 16
Failed: 0
Total changes: 1213
Total time: 45.65s
```

| Metric | Trước | Sau |
|--------|-------|-----|
| Trung bình Quality Score | 85.7 | ~98 |
| Lỗi OCR | 3 | 0 |
| Duplicate lines | 9 | 0 |
| Header artifacts | 160 | 0 |
