"""
Enhanced Embedding Pipeline với Multi-file Support
- Xử lý nhiều files PDF
- Track source file trong metadata
- Sử dụng abstract VectorStore để dễ scale
- Support FAISS (local) → PostgreSQL (production)
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from langchain_huggingface import HuggingFaceEmbeddings
from tqdm import tqdm

from .config import PipelineConfig, DEFAULT_CONFIG
from .vector_store import Document
from .faiss_store import FaissVectorStore, FaissConfig


class EmbeddingPipeline:
    """
    Pipeline để xử lý embedding và lưu vào vector store
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or DEFAULT_CONFIG

        # Initialize embedding model
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.config.embedding.model_name,
            model_kwargs=self.config.embedding.model_kwargs,
            encode_kwargs=self.config.embedding.encode_kwargs,
        )

        # Initialize vector store based on config
        self.vector_store = self._init_vector_store()

        if self.config.verbose:
            print(f"✅ Initialized EmbeddingPipeline")
            print(f"   Model: {self.config.embedding.model_name}")
            print(f"   Device: {self.config.embedding.device}")
            print(f"   Vector Store: {self.config.vector_store.store_type}")

    def _init_vector_store(self):
        """Initialize vector store based on config"""
        if self.config.vector_store.store_type == "faiss":
            faiss_config = FaissConfig(
                index_type=self.config.vector_store.faiss_index_type,
                dimension=self.config.vector_store.dimension,
                save_path=self.config.chunks.vector_store_dir,
                use_gpu=self.config.vector_store.use_gpu,
            )
            return FaissVectorStore(faiss_config)

        # Future: PostgreSQL, ChromaDB, etc.
        elif self.config.vector_store.store_type == "postgres":
            raise NotImplementedError("PostgreSQL support coming soon!")

        else:
            raise ValueError(
                f"Unknown store type: {self.config.vector_store.store_type}"
            )

    def build_embedding_input_optimized(self, chunk: Dict[str, Any]) -> str:
        """
        Tối ưu cho E5 model:
        - Natural language structure
        - No weird tags
        - Hierarchical context
        """
        meta = chunk["metadata"]
        content = chunk["content"].strip()

        # Build context hierarchy
        context_parts = []

        # Add chapter (if exists and meaningful)
        chapter = meta.get("chapter_full") or ""
        if chapter and isinstance(chapter, str):
            chapter = chapter.strip()
            if chapter:
                context_parts.append(chapter)

        # Add article (if exists)
        article = meta.get("article_full") or ""
        if article and isinstance(article, str):
            article = article.strip()
            if article:
                context_parts.append(article)

        # Add clause number (if not default/first clause)
        clause = meta.get("clause") or ""
        if clause and isinstance(clause, str):
            clause = clause.strip()
            if clause and clause not in ["", "1"]:
                context_parts.append(f"Khoản {clause}")

        # Construct final text
        if context_parts:
            # Natural language: "context quy định: content"
            context_str = ", ".join(context_parts)
            final_text = f"{context_str} quy định:\n\n{content}"
        else:
            final_text = content

        return final_text

    def build_embedding_input_alternative(self, chunk: Dict[str, Any]) -> str:
        """
        Alternative structure: More structured but still natural
        """
        meta = chunk["metadata"]
        content = chunk["content"].strip()

        parts = []

        # Title (document level)
        title = meta.get("title")
        if title and isinstance(title, str) and title.strip():
            parts.append(f"{title.strip()}\n")

        # Chapter and Article in one line
        location = []
        chapter = meta.get("chapter_full")
        if chapter and isinstance(chapter, str) and chapter.strip():
            location.append(chapter.strip())

        article = meta.get("article_full")
        if article and isinstance(article, str) and article.strip():
            location.append(article.strip())

        if location:
            parts.append(" > ".join(location))
            parts.append("\n")

        # Clause (if not first)
        clause = meta.get("clause")
        if clause and isinstance(clause, str):
            clause = clause.strip()
            if clause and clause not in ["", "1"]:
                parts.append(f"Khoản {clause}:\n")

        # Content
        parts.append(content)

        return "".join(parts)

    def build_embedding_input(self, chunk: Dict[str, Any]) -> str:
        """
        Choose which structure to use
        Default: optimized version
        """
        if self.config.chunks.context_strategy == "alternative":
            return self.build_embedding_input_alternative(chunk)
        else:
            return self.build_embedding_input_optimized(chunk)

    def load_chunks_from_file(
        self, chunks_file: Union[str, Path], source_file: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Load chunks từ file JSON và thêm source_file vào metadata

        Args:
            chunks_file: Path tới file chunks.json
            source_file: Tên file PDF gốc (nếu None sẽ dùng tên chunks_file)

        Returns:
            List of chunks với source_file đã được thêm vào metadata
        """
        chunks_path = Path(chunks_file)

        if not chunks_path.exists():
            raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

        with open(chunks_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        # Auto-detect source file name nếu không được cung cấp
        if source_file is None:
            # Assume chunks_file is named like "QCDT_2025_chunks.json"
            source_file = chunks_path.stem.replace("_chunks", "")

        # Add source_file to each chunk's metadata
        for chunk in chunks:
            chunk["metadata"]["source_file"] = source_file

        if self.config.verbose:
            print(f"📁 Loaded {len(chunks)} chunks from {chunks_path.name}")
            print(f"   Source file: {source_file}")

        return chunks

    def process_chunks(
        self, chunks: List[Dict[str, Any]], save_intermediate: bool = True
    ) -> List[Document]:
        """
        Xử lý chunks: build embedding input, embed, convert to Document

        Args:
            chunks: List of chunks (đã có source_file trong metadata)
            save_intermediate: Có lưu chunks_with_embeddings.json không

        Returns:
            List of Document objects ready to add to vector store
        """
        if not chunks:
            return []

        # Step 1: Build embedding inputs
        if self.config.verbose:
            print("\n📝 Building embedding inputs...")

        embedding_inputs = []
        for chunk in tqdm(
            chunks, desc="Preparing texts", disable=not self.config.verbose
        ):
            embedding_input = self.build_embedding_input(chunk)

            # Add E5 model instruction prefix if configured
            if self.config.chunks.add_instruction_prefix:
                embedding_input = f"passage: {embedding_input}"

            chunk["embedding_input"] = embedding_input
            embedding_inputs.append(embedding_input)

        # Step 2: Batch embed
        if self.config.verbose:
            print(f"\n🔢 Embedding {len(embedding_inputs)} chunks...")
            print(f"   Using embed_documents() for passages")

        batch_size = self.config.embedding.batch_size
        all_embeddings = []

        for i in tqdm(
            range(0, len(embedding_inputs), batch_size),
            desc="Embedding batches",
            disable=not self.config.verbose,
        ):
            batch = embedding_inputs[i : i + batch_size]
            batch_embeddings = self.embeddings.embed_documents(batch)
            all_embeddings.extend(batch_embeddings)

        # Step 3: Assign embeddings and convert to Documents
        if self.config.verbose:
            print("\n📦 Creating Document objects...")

        documents = []
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = all_embeddings[i]

            # Convert to Document
            doc = Document(
                id=chunk.get("readable_id", f"chunk_{chunk['chunk_id']}"),
                content=chunk["content"],
                embedding=all_embeddings[i],
                metadata=chunk["metadata"],
            )
            documents.append(doc)

        # Step 4: Save intermediate result (optional)
        if save_intermediate and self.config.chunks.save_intermediate:
            source_file = chunks[0]["metadata"].get("source_file", "unknown")
            output_path = (
                Path(self.config.chunks.output_dir)
                / f"{source_file}_chunks_with_embeddings.json"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)

            if self.config.verbose:
                print(f"💾 Saved intermediate result to {output_path.name}")

        return documents

    def process_single_file(
        self,
        chunks_file: Union[str, Path],
        source_file: Optional[str] = None,
        add_to_store: bool = True,
    ) -> List[Document]:
        """
        Xử lý 1 file chunks.json

        Args:
            chunks_file: Path tới file chunks.json
            source_file: Tên file PDF gốc (optional)
            add_to_store: Có thêm vào vector store ngay không

        Returns:
            List of Documents
        """
        # Load chunks
        chunks = self.load_chunks_from_file(chunks_file, source_file)

        # Process
        documents = self.process_chunks(chunks)

        # Add to vector store
        if add_to_store:
            self.vector_store.add_documents(documents)

        return documents

    def process_multiple_files(
        self,
        chunks_files: List[Union[str, Path, tuple]],
        overwrite_existing: Optional[bool] = None,
    ) -> Dict[str, List[Document]]:
        """
        Xử lý nhiều files chunks.json

        Args:
            chunks_files: List of:
                - str/Path: Path tới chunks.json (auto-detect source_file)
                - tuple: (chunks_path, source_file_name)
            overwrite_existing: Có xóa documents cũ của source_file trước không

        Returns:
            Dict mapping source_file -> List of Documents
        """
        overwrite = (
            overwrite_existing
            if overwrite_existing is not None
            else self.config.chunks.overwrite_existing
        )

        all_documents = {}

        for item in chunks_files:
            # Parse input
            if isinstance(item, tuple):
                chunks_file, source_file = item
            else:
                chunks_file = item
                source_file = None

            # Determine source_file for deletion check
            if source_file is None:
                source_file = Path(chunks_file).stem.replace("_chunks", "")

            # Delete existing documents if overwrite
            if overwrite:
                deleted = self.vector_store.delete_by_metadata(
                    {"source_file": source_file}
                )
                if deleted > 0 and self.config.verbose:
                    print(
                        f"🗑️  Deleted {deleted} existing documents from {source_file}"
                    )

            # Process file
            documents = self.process_single_file(
                chunks_file, source_file, add_to_store=True
            )
            all_documents[source_file] = documents

        return all_documents

    def save_vector_store(self, path: Optional[str] = None):
        """Save vector store to disk"""
        self.vector_store.save(path)

        if self.config.verbose:
            stats = self.vector_store.get_statistics()
            print(f"\n📊 Vector Store Statistics:")
            print(f"   Total documents: {stats['total_documents']}")
            print(f"   Source files: {len(stats['source_files'])}")
            for source, count in stats["source_files"].items():
                print(f"      - {source}: {count} chunks")

    def load_vector_store(self, path: Optional[str] = None):
        """Load vector store from disk"""
        self.vector_store.load(path)

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ):
        """
        Search trong vector store

        Args:
            query: Query text
            top_k: Số lượng kết quả (default từ config)
            filters: Metadata filters (e.g., {"source_file": "QCDT_2025"})

        Returns:
            List of SearchResult
        """
        top_k = top_k or self.config.vector_store.default_top_k

        # Add query instruction for E5 model
        if self.config.chunks.add_instruction_prefix:
            query_text = f"query: {query}"
        else:
            query_text = query

        # Embed query
        query_embedding = self.embeddings.embed_query(query_text)

        # Search
        results = self.vector_store.search(query_embedding, top_k, filters)

        return results


# Convenience functions for backward compatibility
def create_pipeline(
    config: Optional[PipelineConfig] = None,
) -> EmbeddingPipeline:
    """Factory function to create pipeline"""
    return EmbeddingPipeline(config)
