# faiss_retriever.py

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Dict
from faiss_vector_store import FAISSVectorStore


class FAISSRetriever:
    """
    Retriever sử dụng FAISS vector store
    """

    def __init__(
        self,
        index_path: str = "./output/faiss.index",
        chunks_path: str = "./output/faiss_chunks.pkl",
        embedding_model: str = "intfloat/multilingual-e5-large",
    ):
        print("🔄 Initializing FAISS Retriever...")

        # Load vector store
        print(f"   Loading vector store...")
        self.vector_store = FAISSVectorStore()
        self.vector_store.load(index_path, chunks_path)

        # Load embedding model
        print(f"   Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model)
        self.is_e5 = "e5" in embedding_model.lower()

        print("✅ Retriever ready!\n")

    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Dict = None,
        include_footnotes: bool = True,
    ) -> List[Dict]:
        """
        Search cho relevant chunks

        Args:
            query: User question
            top_k: Number of results
            filters: Metadata filters (manual filtering after retrieval)
            include_footnotes: Lấy footnotes liên quan không

        Returns:
            List of search results với metadata
        """
        print(f"🔍 Searching: '{query}'")

        # 1. Embed query
        if self.is_e5:
            query_text = f"query: {query}"
        else:
            query_text = query

        query_vector = self.model.encode(
            query_text, normalize_embeddings=True, convert_to_numpy=True
        )

        # 2. Search in FAISS (get more if we need to filter)
        search_k = top_k * 10 if filters else top_k
        raw_results = self.vector_store.search(query_vector, top_k=search_k)

        # 3. Get chunks and apply filters
        results = []

        for idx, score in raw_results:
            chunk = self.vector_store.get_chunk(idx)

            # Apply filters if provided
            if filters:
                skip = False
                for key, value in filters.items():
                    chunk_value = chunk.get("metadata", {}).get(key)
                    if chunk_value != value:
                        skip = True
                        break
                if skip:
                    continue

            # Format result
            result = {
                "score": float(score),
                "index": idx,
                "chunk_id": chunk.get("chunk_id"),
                "chunk_type": chunk.get("chunk_type", "main_content"),
                "content": chunk.get("content"),
                "metadata": chunk.get("metadata", {}),
            }

            # Get footnotes if applicable
            if include_footnotes and chunk.get("chunk_type") == "main_content":
                footnote_refs = chunk.get("metadata", {}).get(
                    "footnote_refs", []
                )
                if footnote_refs:
                    result["footnotes"] = self._get_footnotes(footnote_refs)

            results.append(result)

            # Stop if we have enough results
            if len(results) >= top_k:
                break

        print(f"   Found {len(results)} results\n")

        return results

    def _get_footnotes(self, footnote_refs: List[str]) -> List[Dict]:
        """
        Lấy footnote chunks từ references
        """
        footnotes = []

        # Search for footnote chunks in vector store
        for ref in footnote_refs:
            target_chunk_id = f"footnote_{ref}"

            # Linear search (not efficient but OK for small datasets)
            for i, chunk in enumerate(self.vector_store.chunks):
                if chunk.get("chunk_id") == target_chunk_id:
                    footnotes.append(
                        {"id": ref, "content": chunk.get("content")}
                    )
                    break

        return footnotes

    def search_by_chunk_id(self, chunk_id: str) -> Dict:
        """Tìm chunk theo chunk_id"""
        for i, chunk in enumerate(self.vector_store.chunks):
            if chunk.get("chunk_id") == chunk_id:
                return {"index": i, "chunk": chunk}
        return None

    def search_by_metadata(
        self, metadata_key: str, metadata_value: str, top_k: int = 10
    ) -> List[Dict]:
        """
        Search chunks có metadata matching

        Example:
            search_by_metadata("applies_to", "sinh_vien")
        """
        results = []

        for i, chunk in enumerate(self.vector_store.chunks):
            if chunk.get("metadata", {}).get(metadata_key) == metadata_value:
                results.append(
                    {
                        "index": i,
                        "chunk_id": chunk.get("chunk_id"),
                        "content": chunk.get("content"),
                        "metadata": chunk.get("metadata", {}),
                    }
                )

                if len(results) >= top_k:
                    break

        return results


# ============================================================================
# Test Retriever
# ============================================================================


def test_retriever():
    """
    Test FAISS retriever với các queries
    """
    print("=" * 70)
    print("🧪 TESTING FAISS RETRIEVER")
    print("=" * 70)
    print()

    # Initialize retriever
    retriever = FAISSRetriever()

    # Test queries
    test_cases = [
        {
            "query": "nội dung Điều 4 chương I",
            "top_k": 10,
            "filters": None,
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*70}")
        print(f"TEST CASE {i}")
        print(f"{'='*70}")
        print(f"Query: {test['query']}")
        if test["filters"]:
            print(f"Filters: {test['filters']}")
        print(f"{'-'*70}\n")

        # Search
        results = retriever.search(
            query=test["query"], top_k=test["top_k"], filters=test["filters"]
        )

        # Display results
        for j, result in enumerate(results, 1):
            print(f"Result {j}:")
            print(f"  Score: {result['score']:.4f}")
            print(f"  Chunk ID: {result['chunk_id']}")
            print(f"  Type: {result['chunk_type']}")

            if result["metadata"].get("article"):
                print(f"  Article: {result['metadata']['article']}")

            if result["metadata"].get("applies_to"):
                print(f"  Applies to: {result['metadata']['applies_to']}")

            print(f"  Content preview:")
            print(f"    {result['content'][:200]}...")

            # Show footnotes if any
            if result.get("footnotes"):
                print(f"  Footnotes: {len(result['footnotes'])}")
                for fn in result["footnotes"]:
                    print(f"    [{fn['id']}]: {fn['content'][:100]}...")

            print()

    print("=" * 70)
    print("✅ TESTING COMPLETED")
    print("=" * 70)


def test_metadata_search():
    """Test search by metadata"""
    print("\n" + "=" * 70)
    print("🧪 TESTING METADATA SEARCH")
    print("=" * 70)
    print()

    retriever = FAISSRetriever()

    # Test: Find all chunks for sinh_vien
    print("Finding chunks for 'sinh_vien'...")
    results = retriever.search_by_metadata("applies_to", "sinh_vien", top_k=5)

    print(f"Found {len(results)} chunks")
    for i, result in enumerate(results[:3], 1):
        print(f"\n{i}. {result['chunk_id']}")
        print(f"   {result['content'][:150]}...")


if __name__ == "__main__":
    # Run tests
    test_retriever()
    # test_metadata_search()
