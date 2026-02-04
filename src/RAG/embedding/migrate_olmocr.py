"""
Migration Script: Thêm chunks olmOCR vào Vector Store
-----------------------------------------------------
Workflow:
1. Load vector store hiện tại
2. Xác định files trùng lặp giữa docling và olmOCR
3. Xóa các chunks từ docling (giữ olmOCR thay thế)
4. Thêm tất cả chunks olmOCR vào store
5. Save và hiển thị thống kê
"""

from pathlib import Path
import json
from typing import List, Dict, Set
from embedding import create_pipeline


def normalize_filename(filename: str) -> str:
    """
    Chuẩn hóa tên file để so sánh
    Loại bỏ: _converted, _chunks, _clean, _final, v.v.
    """
    name = filename.lower()

    # Remove extensions
    name = name.replace(".json", "")
    name = name.replace(".md", "")

    # Remove common suffixes
    suffixes = [
        "_converted_chunks",
        "_converted",
        "_chunks",
        "_clean",
        "_final",
        "clean",
    ]

    for suffix in suffixes:
        name = name.replace(suffix, "")

    # Remove leading numbers and dots (e.g., "1. ", "01_1 ", "06_ ")
    import re

    name = re.sub(r"^[\d_\.\s]+", "", name)

    # Clean up spaces and underscores
    name = name.strip("_").strip()

    return name


def find_duplicate_files(
    existing_sources: List[str], olmocr_files: List[Path]
) -> Dict[str, List[str]]:
    """
    Tìm các file trùng lặp giữa vector store và olmOCR

    Returns:
        Dict với key = normalized name, value = list of matching files
    """
    duplicates = {}

    # Normalize existing sources
    existing_normalized = {}
    for source in existing_sources:
        normalized = normalize_filename(source)
        if normalized not in existing_normalized:
            existing_normalized[normalized] = []
        existing_normalized[normalized].append(source)

    # Check olmOCR files
    for olmocr_file in olmocr_files:
        normalized = normalize_filename(olmocr_file.stem)
        if normalized in existing_normalized:
            duplicates[normalized] = {
                "existing": existing_normalized[normalized],
                "olmocr": olmocr_file.name,
            }

    return duplicates


def load_olmocr_chunk_file(file_path: Path) -> List[Dict]:
    """Load và parse olmOCR chunk file"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """Main migration workflow"""
    print("=" * 70)
    print("🔄 Migration: Thêm chunks olmOCR vào Vector Store")
    print("=" * 70)

    # 1. Load existing vector store
    print("\n📦 BƯỚC 1: Load vector store hiện tại...")
    pipeline = create_pipeline()

    try:
        pipeline.load_vector_store()
        print("✅ Loaded successfully")
    except FileNotFoundError:
        print("⚠️  Không tìm thấy vector store. Tạo mới...")

    # Show current statistics
    try:
        stats = pipeline.vector_store.get_statistics()
        print(f"\n📊 Thống kê hiện tại:")
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Source files: {len(stats['source_files'])}")
        for source, count in stats["source_files"].items():
            print(f"      - {source}: {count} chunks")
    except:
        stats = {"source_files": {}}

    # 2. Find olmOCR files
    print("\n\n📁 BƯỚC 2: Tìm các file olmOCR chunks...")
    olmocr_dir = Path("../olmocr_chunks")

    if not olmocr_dir.exists():
        print(f"❌ Không tìm thấy thư mục: {olmocr_dir}")
        return

    olmocr_files = list(olmocr_dir.glob("*_converted_chunks.json"))
    print(f"✅ Tìm thấy {len(olmocr_files)} files olmOCR")

    # 3. Identify duplicates
    print("\n\n🔍 BƯỚC 3: Xác định files trùng lặp...")
    existing_sources = list(stats.get("source_files", {}).keys())
    duplicates = find_duplicate_files(existing_sources, olmocr_files)

    if duplicates:
        print(f"\n⚠️  Tìm thấy {len(duplicates)} files trùng lặp:")
        for normalized, files in duplicates.items():
            print(f"\n   {normalized}:")
            print(f"      Trong store: {files['existing']}")
            print(f"      Từ olmOCR:   {files['olmocr']}")

        # Ask for confirmation
        response = input(
            "\n❓ Xóa các file cũ và thay thế bằng olmOCR? (y/n): "
        )
        if response.lower() != "y":
            print("❌ Hủy migration")
            return

        # 4. Delete duplicates from store
        print("\n\n🗑️  BƯỚC 4: Xóa files trùng lặp khỏi vector store...")
        for normalized, files in duplicates.items():
            for existing_source in files["existing"]:
                print(f"   Deleting: {existing_source}")
                deleted_count = pipeline.vector_store.delete_by_metadata(
                    {"source_file": existing_source}
                )
                print(f"   ✅ Deleted {deleted_count} chunks")
    else:
        print("✅ Không có file trùng lặp")

    # 5. Add all olmOCR files
    print("\n\n➕ BƯỚC 5: Thêm tất cả chunks olmOCR...")

    total_added = 0
    for olmocr_file in olmocr_files:
        # Extract source name (remove _converted_chunks.json)
        source_name = olmocr_file.stem.replace("_converted_chunks", "")

        print(f"\n   Processing: {olmocr_file.name}")
        print(f"   Source name: {source_name}")

        try:
            documents = pipeline.process_single_file(
                chunks_file=str(olmocr_file),
                source_file=source_name,
                add_to_store=True,
            )
            print(f"   ✅ Added {len(documents)} chunks")
            total_added += len(documents)
        except Exception as e:
            print(f"   ❌ Error: {e}")
            continue

    print(
        f"\n✅ Tổng cộng đã thêm: {total_added} chunks từ {len(olmocr_files)} files"
    )

    # 6. Save vector store
    print("\n\n💾 BƯỚC 6: Save vector store...")
    pipeline.save_vector_store()

    # 7. Show final statistics
    print("\n\n📊 THỐNG KÊ CUỐI CÙNG:")
    print("=" * 70)
    final_stats = pipeline.vector_store.get_statistics()

    print(f"\nTotal documents: {final_stats['total_documents']}")
    print(f"Unique chunks: {final_stats['unique_chunk_ids']}")
    print(f"\nSource files: {len(final_stats['source_files'])}")

    # Sort by count
    sorted_sources = sorted(
        final_stats["source_files"].items(), key=lambda x: x[1], reverse=True
    )

    for source, count in sorted_sources:
        print(f"   - {source}: {count} chunks")

    print(f"\nLevels distribution:")
    for level, count in final_stats["levels"].items():
        print(f"   - {level}: {count}")

    print("\n" + "=" * 70)
    print("✅ MIGRATION HOÀN TẤT!")
    print("=" * 70)


if __name__ == "__main__":
    main()
