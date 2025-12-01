# faiss_setup.py - Fixed version

import faiss
import numpy as np
import json
import pickle
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class FAISSVectorStore:
    """
    FAISS Vector Store cho Quy chế ĐHBK
    Fixed: Proper normalization, validation, metadata
    """

    def __init__(self):
        self.index = None
        self.chunks = None
        self.dimension = None
        self.index_type = None

    def create_from_chunks(
        self,
        chunks_path: str = "./output/chunks_with_embeddings_2.json",
        use_approximate: bool = False,
    ):
        """
        Tạo FAISS index từ file chunks có embeddings

        Args:
            chunks_path: Path to chunks_embedded.json
            use_approximate: Use IVF for large datasets (>10K vectors)
        """
        print("🔄 Creating FAISS index from chunks...")

        # Load chunks
        print(f"   Loading chunks from: {chunks_path}")
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.chunks = json.load(f)

        print(f"   Loaded {len(self.chunks)} chunks")

        # Validate and extract embeddings
        embeddings = []
        invalid_chunks = []

        for i, chunk in enumerate(self.chunks):
            # Check embedding exists
            if "embedding" not in chunk:
                invalid_chunks.append((i, "missing embedding"))
                continue

            emb = chunk["embedding"]

            # Check embedding is list/array
            if not isinstance(emb, (list, np.ndarray)):
                invalid_chunks.append((i, f"invalid type: {type(emb)}"))
                continue

            # Check dimension consistency
            if embeddings and len(emb) != len(embeddings[0]):
                invalid_chunks.append(
                    (i, f"dim mismatch: {len(emb)} vs {len(embeddings[0])}")
                )
                continue

            embeddings.append(emb)

        # Report invalid chunks
        if invalid_chunks:
            print(f"   ⚠️  Found {len(invalid_chunks)} invalid chunks:")
            for idx, reason in invalid_chunks[:5]:
                print(f"      - Chunk {idx}: {reason}")
            if len(invalid_chunks) > 5:
                print(f"      ... and {len(invalid_chunks) - 5} more")
            raise ValueError(f"Found {len(invalid_chunks)} invalid chunks!")

        # Convert to numpy array
        embeddings_np = np.array(embeddings, dtype="float32")
        print(f"   Embeddings shape: {embeddings_np.shape}")

        # Get dimension
        self.dimension = embeddings_np.shape[1]
        print(f"   Embedding dimension: {self.dimension}")

        # ✅ CRITICAL: Normalize embeddings for cosine similarity
        print(f"   Normalizing embeddings for cosine similarity...")
        faiss.normalize_L2(embeddings_np)  # In-place normalization

        # Verify normalization
        norms = np.linalg.norm(embeddings_np, axis=1)
        print(
            f"   After normalization - norms: min={norms.min():.4f}, max={norms.max():.4f}"
        )

        # Create FAISS index
        if use_approximate and len(embeddings_np) > 10000:
            self._create_ivf_index(embeddings_np)
        else:
            self._create_flat_index(embeddings_np)

        print(f"✅ FAISS index created!")
        print(f"   Total vectors: {self.index.ntotal}")
        print(f"   Index type: {self.index_type}\n")

        return self

    def _create_flat_index(self, embeddings_np: np.ndarray):
        """Create exact search index (IndexFlatIP)"""
        print(f"   Creating IndexFlatIP (exact search)...")
        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(embeddings_np)
        self.index_type = "IndexFlatIP"

    def _create_ivf_index(self, embeddings_np: np.ndarray):
        """Create approximate search index (IVF)"""
        # Number of clusters
        nlist = int(np.sqrt(len(embeddings_np)))
        nlist = max(100, min(nlist, 10000))

        print(
            f"   Creating IndexIVFFlat (approximate search, nlist={nlist})..."
        )

        # Create quantizer
        quantizer = faiss.IndexFlatIP(self.dimension)

        # Create IVF index
        self.index = faiss.IndexIVFFlat(
            quantizer, self.dimension, nlist, faiss.METRIC_INNER_PRODUCT
        )

        # Train
        print(f"   Training index...")
        self.index.train(embeddings_np)

        # Add vectors
        self.index.add(embeddings_np)

        # Set search parameters
        self.index.nprobe = min(10, nlist // 10)

        self.index_type = (
            f"IndexIVFFlat(nlist={nlist}, nprobe={self.index.nprobe})"
        )

    def save(
        self,
        index_path: str = "./output/faiss_2.index",
        chunks_path: str = "./output/faiss_chunks_2.pkl",
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

        # ✅ Save chunks + metadata
        metadata = {
            "chunks": self.chunks,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "total_vectors": self.index.ntotal,
            "created_at": str(np.datetime64("now")),
        }

        with open(chunks_path, "wb") as f:
            pickle.dump(metadata, f)
        print(f"   ✅ Saved chunks + metadata: {chunks_path}")

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
        index_path: str = "./output/faiss_2.index",
        chunks_path: str = "./output/faiss_chunks_2.pkl",
    ):
        """
        Load FAISS index và chunks từ file
        """
        print("📂 Loading FAISS index and chunks...")

        # Load index
        self.index = faiss.read_index(index_path)
        print(f"   ✅ Loaded index: {self.index.ntotal} vectors")

        # Load chunks + metadata
        with open(chunks_path, "rb") as f:
            data = pickle.load(f)

        # Handle both old and new format
        if isinstance(data, dict):
            self.chunks = data
            self.dimension = data.get("dimension", self.index.d)
            self.index_type = data.get("index_type", "unknown")
            print(f"   ✅ Loaded chunks: {len(self.chunks)} items")
            print(f"   📊 Metadata:")
            print(f"      - Index type: {self.index_type}")
            print(f"      - Created at: {data.get('created_at')}")
        else:
            # Old format
            self.chunks = data
            self.dimension = self.index.d
            self.index_type = type(self.index).__name__
            print(f"   ✅ Loaded chunks (old format): {len(self.chunks)} items")

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

        # ✅ CRITICAL: Normalize query vector
        faiss.normalize_L2(query_vector)

        # Search
        distances, indices = self.index.search(query_vector, top_k)

        # Filter invalid indices and return
        results = [
            (int(idx), float(dist))
            for idx, dist in zip(indices[0], distances[0])
            if idx != -1  # Filter out invalid indices
        ]

        return results

    def search_with_filter(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[Tuple[int, float, Dict]]:
        """
        Search với metadata filtering

        Args:
            query_vector: Query embedding
            top_k: Number of results
            filters: Dict of filters, e.g. {"chapter": "I", "article": "1"}

        Returns:
            List of (index, score, chunk) tuples
        """
        # Get more candidates for filtering
        k_retrieve = top_k * 10 if filters else top_k

        # Basic search
        candidates = self.search(query_vector, k_retrieve)

        # Apply filters
        if filters:
            filtered = []
            for idx, score in candidates:
                chunk = self.get_chunk(idx)
                metadata = chunk.get("metadata", {})

                # Check all filter conditions
                match = all(
                    metadata.get(key) == value for key, value in filters.items()
                )

                if match:
                    filtered.append((idx, score, chunk))

                if len(filtered) >= top_k:
                    break

            return filtered[:top_k]
        else:
            return [
                (idx, score, self.get_chunk(idx)) for idx, score in candidates
            ]

    def batch_search(
        self, query_vectors: np.ndarray, top_k: int = 5
    ) -> List[List[Tuple[int, float]]]:
        """
        Batch search multiple queries

        Args:
            query_vectors: 2D array of shape (n_queries, dimension)
            top_k: Number of results per query

        Returns:
            List of results for each query
        """
        # Ensure correct shape
        if len(query_vectors.shape) == 1:
            query_vectors = query_vectors.reshape(1, -1)

        # Ensure float32
        query_vectors = query_vectors.astype("float32")

        # Normalize
        faiss.normalize_L2(query_vectors)

        # Batch search
        distances, indices = self.index.search(query_vectors, top_k)

        # Format results
        results = []
        for i in range(len(query_vectors)):
            query_results = [
                (int(idx), float(dist))
                for idx, dist in zip(indices[i], distances[i])
                if idx != -1
            ]
            results.append(query_results)

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
        print(f"Index type: {self.index_type}")

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
    vector_store.create_from_chunks(
        CHUNKS_EMBEDDED_PATH, use_approximate=False  # Set True for >10K vectors
    )

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

    # Step 5: Test search
    print("\nSTEP 5: Test Search")
    print("-" * 70)

    # Create a dummy query vector for testing
    print("   Creating test query...")
    test_query = np.random.randn(test_store.dimension).astype("float32")

    print("   Searching...")
    results = test_store.search(test_query, top_k=3)

    print(f"   ✅ Search successful! Found {len(results)} results")
    for i, (idx, score) in enumerate(results, 1):
        chunk = test_store.get_chunk(idx)
        content_preview = chunk.get("content", "")[:100]
        print(f"   {i}. Score: {score:.4f} | Preview: {content_preview}...")

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
