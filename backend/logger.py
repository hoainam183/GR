"""
CSV Logger for RAG System
Logs questions, retrieved documents, and answers
"""

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json


class RAGLogger:
    """Logger to save RAG interactions to CSV"""

    def __init__(self, log_file: str = "rag_logs.csv"):
        """
        Initialize logger

        Args:
            log_file: Path to CSV log file
        """
        self.log_file = Path(log_file)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Create CSV file with headers if it doesn't exist"""
        if not self.log_file.exists():
            with open(
                self.log_file, "w", newline="", encoding="utf-8-sig"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "question",
                        "num_retrieved_docs",
                        "retrieved_docs",
                        "model_name",
                    ]
                )

    def log(self, question: str, sources: List[Dict], model_name: str):
        """
        Log a RAG interaction

        Args:
            question: User's question
            sources: List of retrieved documents
            model_name: Name of LLM model used
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        num_docs = len(sources)

        # Format retrieved docs - only content, separated by newlines
        retrieved_contents = []
        for i, source in enumerate(sources, 1):
            content = source.get("content", "")
            # Add rank prefix for clarity
            retrieved_contents.append(f"[{i}] {content}")

        # Join with double newline for readability
        retrieved_docs_text = "\n\n".join(retrieved_contents)

        # Write to CSV with UTF-8 BOM for Excel compatibility
        with open(self.log_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    timestamp,
                    question,
                    num_docs,
                    retrieved_docs_text,
                    model_name,
                ]
            )

        print(f"✅ Logged to {self.log_file}")


# Example usage
if __name__ == "__main__":
    logger = RAGLogger("test_logs.csv")

    # Test log
    sources = [
        {
            "content": "Test content 1",
            "score": 0.95,
            "metadata": {"source_file": "test.pdf", "article": "Điều 1"},
        },
        {
            "content": "Test content 2",
            "score": 0.87,
            "metadata": {"source_file": "test2.pdf", "article": "Điều 2"},
        },
    ]

    logger.log(
        question="Test question?",
        sources=sources,
        model_name="gemini-2.5-flash",
    )

    print("Test completed!")
