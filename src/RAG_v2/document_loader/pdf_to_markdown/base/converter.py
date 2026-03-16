# pdf_to_markdown/base/converter.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class BasePDFConverter(ABC):
    """Base class cho tất cả các PDF converter"""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def convert(self, pdf_path: Path) -> Dict[str, Any]:
        """Convert một PDF và trả về metadata + nội dung"""
        pass

    def _save_markdown(self, content: str, stem: str) -> Path:
        md_path = self.output_dir / f"{stem}.md"
        md_path.write_text(content, encoding="utf-8")
        return md_path

    def _save_metadata(self, metadata: Dict[str, Any], stem: str) -> Path:
        json_path = self.output_dir / f"{stem}_metadata.json"
        import json

        json_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return json_path

    def _get_stats(self, content: str, extra: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "conversion_time": now,
            "num_chars": len(content),
            "num_lines": len(content.splitlines()),
            "status": "success",
            **extra,
        }
