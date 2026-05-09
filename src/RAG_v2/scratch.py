import sys
import os

# Set working directory to allow imports
sys.path.insert(0, "/Users/nam.nguyen/Documents/personal/GR/src/RAG_v2")

from retrieval.metadata_filters import KeHoachFilterExtractor

extractor = KeHoachFilterExtractor()

test_queries = [
    "ĐĂNG KÝ KẾ HOẠCH HỌC TẬP KỲ HÈ NĂM HỌC 2025-2026 (20253) VÀ KỲ 1 NĂM HỌC 2026-2027 (20261)",
    "kế hoạch học tập năm học 2025-2026",
    "học kỳ hè 2025/2026 tuyển sinh",
    "Kế hoạch năm 2025",
    "Thông báo tháng 3 năm 2026",
    "Lịch đăng ký tháng 4/2026",
]

for q in test_queries:
    res = extractor.extract(q)
    print(f"Query: {q}")
    print(f"  Result ES queries: {res.metadata_es_queries}\n")
