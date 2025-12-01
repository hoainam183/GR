from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import re
from pathlib import Path
import json
from collections import Counter


# =============================================================================
# BASE CLASS: DocumentChunker
# =============================================================================
class DocumentChunker(ABC):
    """
    Base class for document chunking strategies
    """

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunks = []

    @abstractmethod
    def parse(self, text: str) -> List[Dict]:
        """Parse document and create chunks"""
        pass

    @abstractmethod
    def split_oversized_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Split chunks that exceed size limit"""
        pass

    def add_chunk_ids(self, chunks: List[Dict]) -> List[Dict]:
        """Add unique IDs to chunks"""
        for idx, chunk in enumerate(chunks):
            chunk["chunk_id"] = f"chunk_{idx:04d}"
        return chunks

    def validate_chunks(self, chunks: List[Dict]) -> Dict:
        """Validate chunk quality and return statistics"""
        total_chunks = len(chunks)
        if total_chunks == 0:
            return {"total_chunks": 0}

        chunk_sizes = [c["metadata"]["chunk_size"] for c in chunks]
        avg_size = sum(chunk_sizes) / len(chunk_sizes)

        stats = {
            "total_chunks": total_chunks,
            "avg_size": avg_size,
            "min_size": min(chunk_sizes),
            "max_size": max(chunk_sizes),
            "chunk_sizes": chunk_sizes,
        }

        return stats

    def save_chunks(self, chunks: List[Dict], output_path: str):
        """Save chunks to JSON file"""
        print(f"💾 Đang lưu {len(chunks)} chunks...")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)

        print(f"✅ Đã lưu: {output_path}\n")

    def chunk_document(self, text: str) -> List[Dict]:
        """Main chunking pipeline"""
        # 1. Parse
        chunks = self.parse(text)

        # 2. Post-process
        chunks = self.post_process_chunks(chunks)

        # 3. Split oversized
        chunks = self.split_oversized_chunks(chunks)

        # 4. Add IDs
        chunks = self.add_chunk_ids(chunks)

        return chunks

    def post_process_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Optional post-processing hook"""
        return chunks
