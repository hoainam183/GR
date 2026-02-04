"""
FAISS Vector Store Implementation
FAISS = Facebook AI Similarity Search
- Fast, efficient, local
- Good cho development và small-medium datasets
- Easy to migrate to production DB later
"""

import os
import json
import pickle
import sys
import numpy as np
import faiss
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from .vector_store import VectorStore, Document, SearchResult, VectorStoreConfig


# Pickle compatibility: Handle old module paths
class _CompatibilityUnpickler(pickle.Unpickler):
    """Custom unpickler that redirects old module paths to new ones"""

    def find_class(self, module, name):
        # Redirect old module paths to src.RAG.embedding
        redirects = {
            "vector_store": "src.RAG.embedding.vector_store",
            "faiss_store": "src.RAG.embedding.faiss_store",
            "embedding.vector_store": "src.RAG.embedding.vector_store",
            "embedding.faiss_store": "src.RAG.embedding.faiss_store",
            "embedding.chunking": "src.RAG.embedding.chunking",
        }

        for old_path, new_path in redirects.items():
            if module.startswith(old_path):
                module = module.replace(old_path, new_path, 1)
                break

        return super().find_class(module, name)


@dataclass
class FaissConfig(VectorStoreConfig):
    """Configuration cho FAISS vector store"""

    index_type: str = (
        "IndexFlatIP"  # Inner Product (cho normalized vectors = cosine similarity)
    )
    dimension: int = 1024  # multilingual-e5-large = 1024
    save_path: str = "./vector_store"
    use_gpu: bool = False

    def validate(self) -> None:
        """Validate config"""
        if self.dimension <= 0:
            raise ValueError("Dimension must be positive")

        # Check if GPU available if requested
        if self.use_gpu and not faiss.get_num_gpus() > 0:
            raise ValueError("GPU requested but not available")


class FaissVectorStore(VectorStore):
    """
    FAISS implementation với metadata filtering

    Architecture:
    - FAISS index: Stores vectors, returns indices
    - Metadata store: Dict mapping index -> metadata
    - ID mapping: Dict mapping chunk_id -> index
    """

    def __init__(self, config: FaissConfig):
        self.config = config
        self.config.validate()

        # Initialize FAISS index
        if config.index_type == "IndexFlatIP":
            # Inner Product (best for normalized vectors)
            self.index = faiss.IndexFlatIP(config.dimension)
        elif config.index_type == "IndexFlatL2":
            # L2 distance
            self.index = faiss.IndexFlatL2(config.dimension)
        else:
            raise ValueError(f"Unsupported index type: {config.index_type}")

        # Move to GPU if requested
        if config.use_gpu:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)

        # Metadata storage
        self.id_to_index: Dict[str, int] = {}  # chunk_id -> FAISS index
        self.index_to_metadata: Dict[int, Dict[str, Any]] = (
            {}
        )  # FAISS index -> full metadata
        self.documents: Dict[str, Document] = (
            {}
        )  # chunk_id -> Document (for easy access)

    def add_documents(
        self, documents: List[Document], batch_size: int = 100
    ) -> None:
        """
        Add documents to FAISS
        """
        if not documents:
            return

        print(f"Adding {len(documents)} documents to FAISS...")

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]

            # Convert embeddings to numpy array
            embeddings = np.array(
                [doc.embedding for doc in batch], dtype=np.float32
            )

            # Get current index position
            current_idx = self.index.ntotal

            # Add to FAISS
            self.index.add(embeddings)

            # Store metadata
            for j, doc in enumerate(batch):
                faiss_idx = current_idx + j
                self.id_to_index[doc.id] = faiss_idx

                # Store full metadata including content
                full_metadata = {
                    "chunk_id": doc.id,
                    "content": doc.content,
                    **doc.metadata,
                }
                self.index_to_metadata[faiss_idx] = full_metadata
                self.documents[doc.id] = doc

        print(
            f"✅ Added {len(documents)} documents. Total: {self.index.ntotal}"
        )

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Semantic search with metadata filtering
        """
        if self.index.ntotal == 0:
            return []

        # Convert query to numpy
        query_vector = np.array([query_embedding], dtype=np.float32)

        # Search FAISS (get more results if filtering)
        search_k = top_k * 10 if filters else top_k
        search_k = min(search_k, self.index.ntotal)

        scores, indices = self.index.search(query_vector, search_k)

        # Convert to SearchResults
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for not found
                continue

            metadata = self.index_to_metadata.get(int(idx))
            if not metadata:
                continue

            # Apply metadata filters
            if filters and not self._match_filters(metadata, filters):
                continue

            result = SearchResult(
                chunk_id=metadata["chunk_id"],
                content=metadata["content"],
                metadata={
                    k: v
                    for k, v in metadata.items()
                    if k not in ["chunk_id", "content"]
                },
                score=float(score),
            )
            results.append(result)

            # Stop if we have enough results
            if len(results) >= top_k:
                break

        return results[:top_k]

    def _match_filters(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """
        Check if metadata matches all filters
        Supports: exact match, list membership
        """
        for key, value in filters.items():
            meta_value = metadata.get(key)

            # Handle list of acceptable values
            if isinstance(value, list):
                if meta_value not in value:
                    return False
            # Exact match
            elif meta_value != value:
                return False

        return True

    def delete_by_metadata(self, filters: Dict[str, Any]) -> int:
        """
        Delete documents by metadata
        Note: FAISS doesn't support deletion, so we rebuild index
        """
        if not filters:
            return 0

        # Find matching documents
        to_keep = []
        deleted_count = 0

        for doc_id, doc in self.documents.items():
            full_metadata = {
                "chunk_id": doc.id,
                "content": doc.content,
                **doc.metadata,
            }

            if self._match_filters(full_metadata, filters):
                deleted_count += 1
            else:
                to_keep.append(doc)

        if deleted_count > 0:
            print(
                f"Rebuilding index after deleting {deleted_count} documents..."
            )

            # Rebuild index
            self.__init__(self.config)
            self.add_documents(to_keep)

        return deleted_count

    def save(self, path: Optional[str] = None) -> None:
        """
        Save FAISS index and metadata to disk
        """
        save_dir = path or self.config.save_path
        os.makedirs(save_dir, exist_ok=True)

        # Save FAISS index
        index_path = os.path.join(save_dir, "faiss.index")

        # GPU index needs to be moved to CPU before saving
        if self.config.use_gpu:
            cpu_index = faiss.index_gpu_to_cpu(self.index)
            faiss.write_index(cpu_index, index_path)
        else:
            faiss.write_index(self.index, index_path)

        # Save metadata
        metadata_path = os.path.join(save_dir, "metadata.pkl")
        with open(metadata_path, "wb") as f:
            pickle.dump(
                {
                    "id_to_index": self.id_to_index,
                    "index_to_metadata": self.index_to_metadata,
                    "documents": self.documents,
                    "config": {
                        "index_type": self.config.index_type,
                        "dimension": self.config.dimension,
                        "save_path": self.config.save_path,
                        "use_gpu": self.config.use_gpu,
                    },
                },
                f,
            )

        # Save human-readable stats
        stats_path = os.path.join(save_dir, "stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(self.get_statistics(), f, ensure_ascii=False, indent=2)

        print(f"✅ Saved vector store to {save_dir}")

    def load(self, path: Optional[str] = None) -> None:
        """
        Load FAISS index and metadata from disk
        """
        load_dir = path or self.config.save_path

        # Load FAISS index
        # embedding_dir = Path(__file__).parent
        # load_dir = embedding_dir / load_dir.lstrip("./")
        # load_dir = str(load_dir)
        index_path = os.path.join(load_dir, "faiss.index")
        print(index_path)
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index not found at {index_path}")

        self.index = faiss.read_index(index_path)

        # Move to GPU if needed
        if self.config.use_gpu:
            res = faiss.StandardGpuResources()
            self.index = faiss.index_cpu_to_gpu(res, 0, self.index)

        # Load metadata with pickle compatibility
        metadata_path = os.path.join(load_dir, "metadata.pkl")
        with open(metadata_path, "rb") as f:
            try:
                data = pickle.load(f)
            except ModuleNotFoundError as e:
                # Try loading with compatibility unpickler
                print(
                    f"⚠️  Module path changed, attempting compatibility load..."
                )
                f.seek(0)
                data = _CompatibilityUnpickler(f).load()

            self.id_to_index = data["id_to_index"]
            self.index_to_metadata = data["index_to_metadata"]
            self.documents = data["documents"]

        print(f"✅ Loaded vector store from {load_dir}")
        print(f"   Total documents: {self.index.ntotal}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store
        """
        # Count documents by source file
        source_files = {}
        levels = {}
        chapters = {}

        for metadata in self.index_to_metadata.values():
            # Source file
            source = metadata.get("source_file", "unknown")
            source_files[source] = source_files.get(source, 0) + 1

            # Level
            level = metadata.get("level", "unknown")
            levels[level] = levels.get(level, 0) + 1

            # Chapter
            chapter = metadata.get("chapter", "N/A")
            if chapter and chapter != "N/A":
                chapters[chapter] = chapters.get(chapter, 0) + 1

        return {
            "total_documents": self.index.ntotal,
            "dimension": self.config.dimension,
            "index_type": self.config.index_type,
            "source_files": source_files,
            "levels": levels,
            "chapters": chapters,
            "unique_chunk_ids": len(self.id_to_index),
        }
