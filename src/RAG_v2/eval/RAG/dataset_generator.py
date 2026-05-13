"""
Dataset Generator — Tạo synthetic Q&A dataset từ Qdrant collections.

Pipeline:
  1. Scroll + sample ngẫu nhiên chunks từ Qdrant
  2. LLM generate câu hỏi + ground truth answer
  3. Lưu JSONL để dùng cho RAGAS eval

Chạy:
    python eval/dataset_generator.py --llm lmstudio
    python eval/dataset_generator.py --llm gemini
    python eval/dataset_generator.py --llm auto --collection ctdt --samples 50
    python eval/dataset_generator.py --llm lmstudio --lmstudio-model qwen3-8b-instruct
    python eval/dataset_generator.py --llm lmstudio --chunks-file data/ctdt/soict/chunks_recursive_parent_child/ITE6_fix_chunks.json --collection ctdt --samples 8
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import random
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

DEFAULT_SAMPLES = 30
DELAY_GEMINI    = 1.5
DELAY_LMSTUDIO  = 0.3

COLLECTION_DESCRIPTIONS: Dict[str, str] = {
    "quydinh": "quy định trường Đại học Bách Khoa Hà Nội về học bổng, ngoại ngữ, điểm rèn luyện, tốt nghiệp và các quy định học vụ",
    "ctdt"   : "chương trình đào tạo các ngành: danh sách môn học, tín chỉ, học phần bắt buộc/tự chọn, học phần tương đương/thay thế",
    "kehoach": "kế hoạch học tập: lịch đăng ký học phần, hạn học bổng, lịch thi giữa kỳ, deadline trong học kỳ",
    "stsv"   : "hỗ trợ sinh viên: thuê nhà, việc làm thêm, biểu mẫu, thủ tục hành chính và dịch vụ sinh viên",
}

_PROMPT = """\
Bạn là chuyên gia tạo dataset đánh giá cho hệ thống RAG đại học Bách Khoa Hà Nội.

Dựa trên đoạn văn bản từ tài liệu về {collection_desc}, hãy tạo {n} cặp câu hỏi - câu trả lời mà sinh viên thực tế có thể hỏi.

Yêu cầu:
- Câu hỏi tự nhiên như sinh viên thực sự viết (có thể không dùng thuật ngữ chính xác).
- Câu trả lời dựa HOÀN TOÀN vào nội dung đoạn văn bản, không thêm thông tin ngoài.
- Đa dạng loại: factoid (hỏi thông tin cụ thể), procedural (hỏi quy trình/cách làm).

Đoạn văn bản:
---
{context}
---
Metadata: {metadata_str}

Trả về JSON thuần (không có markdown fence):
{{"qa_pairs": [{{"question": "...", "answer": "...", "question_type": "factoid|procedural"}}]}}"""


@dataclass
class QAItem:
    question: str
    ground_truth: str
    contexts: List[str]
    context_ids: List[str]
    collection: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    question_type: str = "factoid"


def _generate_qa(judge, chunk_text: str, collection: str, metadata: Dict, n: int = 2) -> List[Dict]:
    meta_str = json.dumps(
        {k: v for k, v in metadata.items()
         if k in (
             "title", "major_name", "major_code", "applicable_major",
             "type_doc", "section_context", "date_str", "doc_title",
             "document_type", "section_h1", "section_h2", "section_h3",
             "section_h4", "hierarchy_path", "level",
         )},
        ensure_ascii=False,
    )
    prompt = _PROMPT.format(
        collection_desc=COLLECTION_DESCRIPTIONS.get(collection, collection),
        n=n,
        context=chunk_text[:2000],
        metadata_str=meta_str or "{}",
    )
    raw = ""
    try:
        raw = judge.generate(prompt, max_tokens=900)
        # Strip markdown fence nếu có
        if "```" in raw:
            parts = raw.split("```")
            raw = parts[1].lstrip("json").strip() if len(parts) > 1 else raw
        return json.loads(raw).get("qa_pairs", [])
    except Exception as e:
        logger.warning("Q&A generation failed: %s | raw[:100]=%s", e, raw[:100])
        return []


def _scroll_sample(qdrant, collection: str, n: int, min_len: int = 150, seed: int = 42) -> List[Dict]:
    points = []
    offset = None
    while True:
        results, next_offset = qdrant.scroll(
            collection_name=collection, limit=200, offset=offset,
            with_payload=True, with_vectors=False,
        )
        for pt in results:
            payload = dict(pt.payload or {})
            text = payload.get("text", "")
            if len(text) >= min_len:
                points.append({
                    "id": str(pt.id),
                    "text": text,
                    "metadata": {k: v for k, v in payload.items() if k != "text"},
                })
        if next_offset is None:
            break
        offset = next_offset
    logger.info("  '%s': %d valid chunks (len>=%d)", collection, len(points), min_len)
    random.seed(seed)
    return random.sample(points, min(n, len(points)))


def _load_chunks_from_file(
    chunks_file: Path,
    n: int,
    min_len: int = 150,
    seed: int = 42,
    include_parent: bool = False,
) -> List[Dict[str, Any]]:
    if not chunks_file.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_file}")

    raw = json.loads(chunks_file.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected a JSON array in {chunks_file}")

    points: List[Dict[str, Any]] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            continue

        text = item.get("content") or item.get("text") or ""
        if not isinstance(text, str) or len(text) < min_len:
            continue

        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        if (not include_parent) and metadata.get("level") == "parent":
            continue

        point_id = str(
            item.get("id")
            or item.get("chunk_id")
            or item.get("readable_id")
            or f"row_{idx:04d}"
        )
        points.append(
            {
                "id": point_id,
                "text": text,
                "metadata": metadata,
            }
        )

    if not points:
        raise ValueError(
            f"No valid chunks found in {chunks_file} (check min_len/include_parent)."
        )

    random.seed(seed)
    sampled = random.sample(points, min(n, len(points)))
    logger.info(
        "Loaded %d valid chunks from file '%s' (sampled=%d, min_len=%d, include_parent=%s)",
        len(points),
        chunks_file,
        len(sampled),
        min_len,
        include_parent,
    )
    return sampled


def _write_dataset(
    judge,
    collection: str,
    chunks: List[Dict[str, Any]],
    output_path: Path,
    n_questions_per_chunk: int,
    mode: str = "w",
) -> int:
    delay = DELAY_GEMINI if "gemini" in judge.name else DELAY_LMSTUDIO
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0

    with open(output_path, mode, encoding="utf-8") as fout:
        logger.info("Generating for %d chunks in '%s' (llm=%s)...", len(chunks), collection, judge.name)
        for i, chunk in enumerate(chunks):
            logger.info("  [%s] %d/%d  id=%s", collection, i + 1, len(chunks), chunk["id"])
            qa_pairs = _generate_qa(judge, chunk["text"], collection, chunk["metadata"], n_questions_per_chunk)
            for qa in qa_pairs:
                if not qa.get("question") or not qa.get("answer"):
                    continue
                item = QAItem(
                    question=qa["question"],
                    ground_truth=qa["answer"],
                    contexts=[chunk["text"]],
                    context_ids=[chunk["id"]],
                    collection=collection,
                    metadata=chunk["metadata"],
                    question_type=qa.get("question_type", "factoid"),
                )
                fout.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
                fout.flush()
                total += 1
            time.sleep(delay)

    logger.info("Done: %d items → %s", total, output_path)
    return total


def generate_dataset(
    judge,
    collections: List[str],
    samples_per_collection: int,
    output_path: Path,
    n_questions_per_chunk: int = 2,
    seed: int = 42,
) -> int:
    from qdrant_client import QdrantClient
    qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    available = {c.name for c in qdrant.get_collections().collections}
    total = 0
    write_mode = "w"
    for col in collections:
        if col not in available:
            logger.warning("Collection '%s' not found — skipping.", col)
            continue
        chunks = _scroll_sample(qdrant, col, samples_per_collection, seed=seed)
        total += _write_dataset(
            judge=judge,
            collection=col,
            chunks=chunks,
            output_path=output_path,
            n_questions_per_chunk=n_questions_per_chunk,
            mode=write_mode,
        )
        write_mode = "a"
    return total


def generate_dataset_from_file(
    judge,
    chunks_file: Path,
    collection: str,
    samples: int,
    output_path: Path,
    n_questions_per_chunk: int = 2,
    seed: int = 42,
    min_len: int = 150,
    include_parent: bool = False,
) -> int:
    chunks = _load_chunks_from_file(
        chunks_file=chunks_file,
        n=samples,
        min_len=min_len,
        seed=seed,
        include_parent=include_parent,
    )
    return _write_dataset(
        judge=judge,
        collection=collection,
        chunks=chunks,
        output_path=output_path,
        n_questions_per_chunk=n_questions_per_chunk,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", choices=["gemini", "lmstudio", "auto"], default="auto")
    parser.add_argument("--collections", nargs="+", default=["quydinh", "ctdt", "kehoach", "stsv"])
    parser.add_argument("--collection", default=None, help="Chỉ 1 collection (override --collections)")
    parser.add_argument(
        "--chunks-file",
        default=None,
        help="Đường dẫn tới *_fix_chunks.json để generate trực tiếp từ file local (không cần Qdrant)",
    )
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--questions-per-chunk", type=int, default=2)
    parser.add_argument("--min-len", type=int, default=150, help="Độ dài tối thiểu của chunk")
    parser.add_argument(
        "--include-parent",
        action="store_true",
        help="Bao gồm chunks có metadata.level=parent khi dùng --chunks-file",
    )
    parser.add_argument("--output", default="eval/data/golden_dataset.jsonl")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--lmstudio-url", default=None)
    parser.add_argument("--lmstudio-model", default=None)
    args = parser.parse_args()

    if args.lmstudio_url:
        os.environ["LMSTUDIO_BASE_URL"] = args.lmstudio_url
    if args.lmstudio_model:
        os.environ["LMSTUDIO_MODEL"] = args.lmstudio_model

    try:
        llm_judge_module = importlib.import_module("eval.llm_judge")
    except ModuleNotFoundError:
        llm_judge_module = importlib.import_module("llm_judge")
    judge = llm_judge_module.LLMJudgeFactory.create(args.llm)
    logger.info("LLM backend: %s", judge.name)

    if args.chunks_file:
        local_collection = args.collection or "ctdt"
        generate_dataset_from_file(
            judge=judge,
            chunks_file=Path(args.chunks_file),
            collection=local_collection,
            samples=args.samples,
            output_path=Path(args.output),
            n_questions_per_chunk=args.questions_per_chunk,
            seed=args.seed,
            min_len=args.min_len,
            include_parent=args.include_parent,
        )
        return

    cols = [args.collection] if args.collection else args.collections
    generate_dataset(
        judge=judge,
        collections=cols,
        samples_per_collection=args.samples,
        output_path=Path(args.output),
        n_questions_per_chunk=args.questions_per_chunk,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()