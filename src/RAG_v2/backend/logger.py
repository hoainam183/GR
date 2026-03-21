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
                        "answer",
                        "model_name",
                    ]
                )

    def log(self, question: str, answer: str, model_name: str):
        """
        Log a RAG interaction

        Args:
            question: User's question
            answer: LLM's answer
            model_name: Name of LLM model used
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Write to CSV with UTF-8 BOM for Excel compatibility
        with open(self.log_file, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    timestamp,
                    question,
                    answer,
                    model_name,
                ]
            )

        print(f"✅ Logged to {self.log_file}")


# Example usage
if __name__ == "__main__":
    logger = RAGLogger("test_logs.csv")

    # Test log
    logger.log(
        question="Test question?",
        answer="This is the LLM's answer to the test question.",
        model_name="gemini-2.5-flash",
    )

    print("Test completed!")
