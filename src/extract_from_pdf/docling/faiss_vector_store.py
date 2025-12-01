# faiss_setup.py

import faiss
import numpy as np
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple


class FAISSVectorStore:
    """
    FAISS Vector Store cho Quy chế ĐHBK
    """

    def __init__(self):
        self.index = None
        self.chunks = None
        self.dimension = None

    def create_from_chunks(
        self, chunks_path: str = "./output/chunks_with_embeddings_2.json"
    ):
        """
        Tạo FAISS index từ file chunks có embeddings

        Args:
            chunks_path: Path to chunks_embedded.json
        """
        print("🔄 Creating FAISS index from chunks...")

        # Load chunks
        print(f"   Loading chunks from: {chunks_path}")
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        print(f"   Loaded {len(self.chunks)} chunks")

        # Extract embeddings
        embeddings = []
        for chunk in self.chunks:
            if "embedding" not in chunk:
                raise ValueError(
                    f"Chunk {chunk.get('chunk_id')} missing embedding!"
                )
            embeddings.append(chunk["embedding"])

        # Convert to numpy array
        embeddings_np = np.array(embeddings, dtype="float32")
        print(f"   Embeddings shape: {embeddings_np.shape}")

        # Get dimension
        self.dimension = embeddings_np.shape[1]
        print(f"   Embedding dimension: {self.dimension}")

        # Create FAISS index
        # IndexFlatIP = Inner Product (for normalized embeddings = cosine similarity)
        print(f"   Creating FAISS IndexFlatIP...")
        self.index = faiss.IndexFlatIP(self.dimension)

        # Add vectors to index
        print(f"   Adding {len(embeddings_np)} vectors to index...")
        self.index.add(embeddings_np)

        print(f"✅ FAISS index created!")
        print(f"   Total vectors: {self.index.ntotal}")
        print(f"   Index type: IndexFlatIP (exact search, cosine similarity)\n")

        return self

    def save(
        self,
        index_path: str = "./output/faiss.index",
        chunks_path: str = "./output/faiss_chunks.pkl",
    ):
        """
        Lưu FAISS index và chunks ra file
        """
        print("💾 Saving FAISS index and chunks...")

        # Ensure directory exists
        Path(index_path).parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, index_path)
        print(f"   ✅ Saved index: {index_path}")

        # Save chunks (metadata)
        with open(chunks_path, "wb") as f:
            pickle.dump(self.chunks, f)
        print(f"   ✅ Saved chunks: {chunks_path}")

        # Print file sizes
        import os

        index_size = os.path.getsize(index_path) / (1024 * 1024)
        chunks_size = os.path.getsize(chunks_path) / (1024 * 1024)

        print(f"\n📊 File sizes:")
        print(f"   Index: {index_size:.2f} MB")
        print(f"   Chunks: {chunks_size:.2f} MB")
        print(f"   Total: {index_size + chunks_size:.2f} MB")

    def load(
        self,
        index_path: str = "./output/faiss.index",
        chunks_path: str = "./output/faiss_chunks.pkl",
    ):
        """
        Load FAISS index và chunks từ file
        """
        print("📂 Loading FAISS index and chunks...")

        # Load index
        self.index = faiss.read_index(index_path)
        print(f"   ✅ Loaded index: {self.index.ntotal} vectors")

        # Load chunks
        with open(chunks_path, "rb") as f:
            self.chunks = pickle.load(f)
        print(f"   ✅ Loaded chunks: {len(self.chunks)} items")

        # Get dimension
        self.dimension = self.index.d
        print(f"   Dimension: {self.dimension}\n")

        return self

    def search(
        self, query_vector: np.ndarray, top_k: int = 5
    ) -> List[Tuple[int, float]]:
        """
        Search trong FAISS index

        Args:
            query_vector: Query embedding (1D numpy array)
            top_k: Number of results

        Returns:
            List of (index, score) tuples
        """
        # Ensure query_vector is correct shape
        if len(query_vector.shape) == 1:
            query_vector = query_vector.reshape(1, -1)

        # Ensure float32
        query_vector = query_vector.astype("float32")

        # Search
        distances, indices = self.index.search(query_vector, top_k)

        # Return as list of tuples
        results = [
            (int(idx), float(dist))
            for idx, dist in zip(indices[0], distances[0])
        ]

        return results

    def get_chunk(self, index: int) -> Dict:
        """Lấy chunk theo index"""
        if index < 0 or index >= len(self.chunks):
            raise IndexError(f"Index {index} out of range")
        return self.chunks[index]

    def get_stats(self):
        """In thống kê về vector store"""
        print("📊 FAISS Vector Store Statistics")
        print("=" * 70)

        if self.index is None:
            print("   No index loaded!")
            return

        print(f"Total vectors: {self.index.ntotal}")
        print(f"Dimension: {self.dimension}")
        print(f"Index type: {type(self.index).__name__}")

        # Chunk statistics
        if self.chunks:
            print(f"\nChunks: {len(self.chunks)}")

            # Count by chunk type
            from collections import Counter

            chunk_types = Counter(
                [c.get("chunk_type", "unknown") for c in self.chunks]
            )
            print(f"\nChunk types:")
            for ctype, count in chunk_types.most_common():
                print(f"  {ctype}: {count}")

            # Average chunk size
            chunk_sizes = [len(c.get("content", "")) for c in self.chunks]
            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            print(f"\nChunk sizes:")
            print(f"  Average: {avg_size:.0f} chars")
            print(f"  Min: {min(chunk_sizes)}")
            print(f"  Max: {max(chunk_sizes)}")

        print("=" * 70)


# ============================================================================
# Setup Script
# ============================================================================


def setup_faiss_vectorstore():
    """
    Script để setup FAISS vector store
    """
    print("=" * 70)
    print("🚀 FAISS VECTOR STORE SETUP")
    print("=" * 70)
    print()

    # Paths
    CHUNKS_EMBEDDED_PATH = "./output/chunks_with_embeddings_2.json"
    FAISS_INDEX_PATH = "./output/faiss_2.index"
    FAISS_CHUNKS_PATH = "./output/faiss_chunks_2.pkl"

    # Check if chunks file exists
    import os

    if not os.path.exists(CHUNKS_EMBEDDED_PATH):
        print(f"❌ Error: {CHUNKS_EMBEDDED_PATH} not found!")
        print(f"   Please run embedding step first.")
        return

    # Step 1: Create FAISS index
    print("STEP 1: Create FAISS Index")
    print("-" * 70)

    vector_store = FAISSVectorStore()
    vector_store.create_from_chunks(CHUNKS_EMBEDDED_PATH)

    # Step 2: Save
    print("\nSTEP 2: Save Index and Chunks")
    print("-" * 70)

    vector_store.save(FAISS_INDEX_PATH, FAISS_CHUNKS_PATH)

    # Step 3: Verify by loading
    print("\nSTEP 3: Verify by Loading")
    print("-" * 70)

    test_store = FAISSVectorStore()
    test_store.load(FAISS_INDEX_PATH, FAISS_CHUNKS_PATH)

    # Step 4: Statistics
    print("\nSTEP 4: Statistics")
    print("-" * 70)

    test_store.get_stats()

    # Summary
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETED!")
    print("=" * 70)
    print(f"\nFiles created:")
    print(f"  📁 {FAISS_INDEX_PATH}")
    print(f"  📁 {FAISS_CHUNKS_PATH}")
    print(f"\nNext step: Build retriever to search")
    print("=" * 70)

    return vector_store


if __name__ == "__main__":
    vector_store = setup_faiss_vectorstore()
