"""
STANDALONE PIPELINE - No Complex Dependencies
==============================================
Simplified version that works without complex import paths

Usage:
    python standalone_pipeline.py "document.pdf"
"""

import sys
from pathlib import Path
import json


def simple_pdf_to_markdown(pdf_path: str) -> str:
    """
    Simple PDF extraction using PyMuPDF only
    No complex dependencies
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install PyMuPDF")

    doc = fitz.open(pdf_path)
    text_parts = []

    for page_num, page in enumerate(doc):
        text = page.get_text()
        text_parts.append(f"## Page {page_num + 1}\n\n{text}\n\n")

    doc.close()
    return "".join(text_parts)


def simple_vietnamese_fix(text: str) -> str:
    """
    Basic Vietnamese text fixes
    """
    import unicodedata

    # Common encoding errors
    fixes = {
        "Ã¡": "á",
        "Ã ": "à",
        "Ã£": "ã",
        "Ã©": "é",
        "Ã¨": "è",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ä'": "đ",
    }

    for wrong, correct in fixes.items():
        text = text.replace(wrong, correct)

    # Unicode normalization
    text = unicodedata.normalize("NFC", text)

    return text


def simple_chunk_by_article(text: str, chunk_size: int = 1500) -> list:
    """
    Simple chunking by "Điều" (Article)
    """
    import re

    chunks = []

    # Find all articles
    article_pattern = re.compile(r"^(?:##\s*)?Điều\s+(\d+)", re.MULTILINE)
    matches = list(article_pattern.finditer(text))

    if not matches:
        # No articles found, chunk by paragraphs
        paragraphs = text.split("\n\n")
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(
                    {
                        "content": current_chunk.strip(),
                        "metadata": {
                            "type": "paragraph_group",
                            "chunk_size": len(current_chunk),
                        },
                    }
                )
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para

        if current_chunk:
            chunks.append(
                {
                    "content": current_chunk.strip(),
                    "metadata": {
                        "type": "paragraph_group",
                        "chunk_size": len(current_chunk),
                    },
                }
            )

        return chunks

    # Chunk by articles
    for i, match in enumerate(matches):
        article_num = match.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        content = text[start:end].strip()

        # Split if too long
        if len(content) > chunk_size * 1.5:
            parts = []
            paragraphs = content.split("\n\n")
            current_part = ""

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                if len(current_part) + len(para) > chunk_size and current_part:
                    parts.append(current_part.strip())
                    current_part = para
                else:
                    current_part += "\n\n" + para if current_part else para

            if current_part:
                parts.append(current_part.strip())

            # Add all parts
            for part_num, part in enumerate(parts, 1):
                chunks.append(
                    {
                        "content": part,
                        "metadata": {
                            "type": "article",
                            "article_number": article_num,
                            "chunk_size": len(part),
                            "is_split": len(parts) > 1,
                            "part_number": part_num if len(parts) > 1 else None,
                        },
                    }
                )
        else:
            chunks.append(
                {
                    "content": content,
                    "metadata": {
                        "type": "article",
                        "article_number": article_num,
                        "chunk_size": len(content),
                    },
                }
            )

    return chunks


def standalone_pipeline(pdf_path: str, output_dir: str = "./simple_output"):
    """
    Complete standalone pipeline
    No complex dependencies
    """
    pdf_file = Path(pdf_path)
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    print(f"\n{'='*60}")
    print(f"🚀 STANDALONE PIPELINE")
    print(f"{'='*60}\n")

    # Check if file exists
    if not pdf_file.exists():
        print(f"❌ File not found: {pdf_path}")
        return

    # STEP 1: Extract text
    print(f"📄 Processing: {pdf_file.name}")
    print(f"🔄 Extracting text...")

    try:
        markdown_text = simple_pdf_to_markdown(str(pdf_file))
        print(f"   ✅ Extracted: {len(markdown_text):,} characters")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return

    # STEP 2: Vietnamese fixes
    print(f"\n🇻🇳 Applying Vietnamese fixes...")
    markdown_text = simple_vietnamese_fix(markdown_text)
    print(f"   ✅ Text processed")

    # Save markdown
    md_file = output_path / f"{pdf_file.stem}.md"
    md_file.write_text(markdown_text, encoding="utf-8")
    print(f"   ✅ Saved: {md_file.name}")

    # STEP 3: Chunk
    print(f"\n✂️  Chunking document...")
    chunks = simple_chunk_by_article(markdown_text)

    # Add IDs and source metadata
    for i, chunk in enumerate(chunks):
        chunk["chunk_id"] = f"chunk_{i:04d}"
        chunk["metadata"]["source_file"] = pdf_file.name
        chunk["metadata"]["position"] = i + 1
        chunk["metadata"]["total_chunks"] = len(chunks)

    print(f"   ✅ Created {len(chunks)} chunks")

    # Calculate stats
    sizes = [c["metadata"]["chunk_size"] for c in chunks]
    avg_size = sum(sizes) / len(sizes) if sizes else 0

    print(f"   ✅ Avg size: {avg_size:.0f} chars")
    print(f"   ✅ Size range: {min(sizes)}-{max(sizes)} chars")

    # STEP 4: Save chunks
    print(f"\n💾 Saving chunks...")
    json_file = output_path / f"{pdf_file.stem}_chunks.json"

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    print(f"   ✅ Saved: {json_file.name}")

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE!")
    print(f"{'='*60}\n")

    print(f"📊 Summary:")
    print(f"   Input: {pdf_file.name}")
    print(f"   Output: {len(chunks)} chunks")
    print(f"   Avg size: {avg_size:.0f} chars")

    print(f"\n📁 Output files:")
    print(f"   - {md_file.name}")
    print(f"   - {json_file.name}")

    print(f"\n🚀 Ready for embedding!")

    return {
        "markdown": str(md_file),
        "chunks": str(json_file),
        "count": len(chunks),
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python standalone_pipeline.py <pdf_file> [output_dir]")
        print("\nExample:")
        print('  python standalone_pipeline.py "document.pdf"')
        print('  python standalone_pipeline.py "document.pdf" "./my_output"')
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./simple_output"

    standalone_pipeline(pdf_path, output_dir)
