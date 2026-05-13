"""
chunk_loader.py — Đọc, lọc và chuẩn bị chunks từ file JSON

Xử lý cấu trúc metadata đặc thù của hai file:
  - ITE6_fix_chunks.json       (chương trình IT Việt-Nhật)
  - Quy định ngoại ngữ K70     (chuẩn ngoại ngữ từ K70)
"""

import json
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .config import EvalConfig, DEFAULT_CONFIG


@dataclass
class Chunk:
    """Đại diện cho một chunk văn bản đã được chuẩn hóa."""
    chunk_id: str
    content: str
    source_file: str
    doc_title: str
    hierarchy_path: str
    section_h2: Optional[str]
    section_h3: Optional[str]
    has_table: bool
    chunk_type: str                        # text | mixed | parent
    level: str                             # parent | child
    major_name: Optional[str] = None
    applicable_major: Optional[list] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def full_context(self) -> str:
        """Trả về nội dung kèm breadcrumb để LLM hiểu ngữ cảnh."""
        breadcrumb = f"[{self.hierarchy_path}]"
        return f"{breadcrumb}\n\n{self.content}"

    @property
    def is_leaf(self) -> bool:
        """Chunk lá (child) thường có nội dung cụ thể hơn."""
        return self.level == "child"


def load_chunks_from_file(file_path: str | Path) -> list[Chunk]:
    """Đọc một file JSON và trả về danh sách Chunk."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    chunks = []
    for item in raw:
        meta = item.get("metadata", {})
        chunk = Chunk(
            chunk_id=item.get("id", item.get("chunk_id", "unknown")),  # UUID "id" ưu tiên
            content=item.get("content", ""),
            source_file=path.name,
            doc_title=meta.get("doc_title", ""),
            hierarchy_path=meta.get("hierarchy_path", ""),
            section_h2=meta.get("section_h2"),
            section_h3=meta.get("section_h3"),
            has_table=meta.get("has_table", False),
            chunk_type=meta.get("chunk_type", "text"),
            level=meta.get("level", "child"),
            major_name=meta.get("major_name"),
            applicable_major=meta.get("applicable_major") or [],
            metadata=meta,
        )
        chunks.append(chunk)

    print(f"  ✓ Đọc {len(chunks)} chunks từ {path.name}")
    return chunks


def filter_chunks(
    chunks: list[Chunk],
    min_size: int = 100,
    exclude_parent_only: bool = True,
    exclude_empty_content: bool = True,
) -> list[Chunk]:
    """
    Lọc các chunks không phù hợp để sinh câu hỏi.

    Args:
        chunks: Danh sách chunk đầu vào
        min_size: Kích thước tối thiểu (ký tự)
        exclude_parent_only: Bỏ parent chunk nếu chỉ có tiêu đề
        exclude_empty_content: Bỏ chunk không có nội dung thực chất
    """
    filtered = []
    skip_counts = {"too_short": 0, "parent_title_only": 0, "empty": 0}

    for chunk in chunks:
        content = chunk.content.strip()

        if not content:
            skip_counts["empty"] += 1
            continue

        if len(content) < min_size:
            skip_counts["too_short"] += 1
            continue

        # Bỏ parent chunk chỉ chứa heading (không có nội dung thực)
        if exclude_parent_only and chunk.level == "parent":
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            meaningful_lines = [l for l in lines if not l.startswith("#") and l != "---"]
            if len(meaningful_lines) < 3:
                skip_counts["parent_title_only"] += 1
                continue

        filtered.append(chunk)

    print(f"  ✓ Lọc: giữ {len(filtered)}/{len(chunks)} chunks")
    print(f"    Bỏ: {skip_counts}")
    return filtered


def sample_chunks_stratified(
    chunks: list[Chunk],
    max_total: int,
    seed: int = 42,
) -> list[Chunk]:
    """
    Lấy mẫu chunks có tầng (stratified) để đảm bảo đa dạng.
    Tầng theo: source_file × has_table × section type
    """
    if not chunks:
        return []

    if max_total <= 0 or max_total >= len(chunks):
        print(f"  ✓ Full mode: dùng toàn bộ {len(chunks)} chunks đã lọc")
        return chunks

    random.seed(seed)

    # Nhóm theo source file để cân bằng hai tài liệu
    by_source: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_source.setdefault(c.source_file, []).append(c)

    per_source = max_total // len(by_source)
    sampled = []

    for src, src_chunks in by_source.items():
        # Ưu tiên chunk có bảng (phong phú thông tin hơn)
        with_table = [c for c in src_chunks if c.has_table]
        without_table = [c for c in src_chunks if not c.has_table]

        n_table = min(len(with_table), per_source // 3)
        n_text = per_source - n_table

        sampled += random.sample(with_table, n_table) if with_table else []
        sampled += random.sample(
            without_table, min(n_text, len(without_table))
        )
        print(f"  ✓ [{src}] lấy {n_table} chunk bảng + {min(n_text, len(without_table))} chunk text")

    return sampled[:max_total]


def load_and_prepare_chunks(config: EvalConfig = DEFAULT_CONFIG) -> list[Chunk]:
    """
    Hàm chính: đọc tất cả file → lọc → lấy mẫu.
    Trả về danh sách chunks sẵn sàng để sinh QA.
    """
    print("\n📂 Đang tải chunks...")
    all_chunks: list[Chunk] = []

    for file_path in config.chunk_files:
        try:
            chunks = load_chunks_from_file(file_path)
            all_chunks.extend(chunks)
        except FileNotFoundError as e:
            print(f"  ⚠️  {e} — bỏ qua")

    if not all_chunks:
        raise ValueError("Không tải được chunk nào! Kiểm tra đường dẫn file.")

    # Lọc
    filtered = filter_chunks(all_chunks, min_size=config.min_chunk_size)

    if not filtered:
        raise ValueError("Không còn chunk hợp lệ sau bước lọc.")

    # Lấy mẫu stratified
    sampled = sample_chunks_stratified(filtered, max_total=config.max_chunks_to_sample)

    print(f"\n✅ Tổng cộng {len(sampled)} chunks sẵn sàng để sinh QA\n")
    return sampled


if __name__ == "__main__":
    # Test nhanh
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    cfg = DEFAULT_CONFIG
    cfg.chunk_files = [
        "../data/ITE6_fix_chunks.json",
        "../data/06__Quy_dinh_ngoai_ngu_K70_chunks.json",
    ]
    chunks = load_and_prepare_chunks(cfg)
    print(f"\nMẫu chunk đầu tiên:\n{chunks[0].full_context[:300]}...")