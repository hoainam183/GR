"""
qa_generator.py — Sinh câu hỏi và ground truth từ chunks

Tạo 4 loại câu hỏi đa dạng phù hợp với tài liệu giáo dục đại học:
  1. factoid      — sự kiện cụ thể (mã học phần, số tín chỉ...)
  2. multi_hop    — cần kết hợp nhiều phần thông tin
  3. comparative  — so sánh hai thứ (tiếng Nhật vs tiếng Anh...)
  4. procedural   — điều kiện, quy trình, lộ trình
"""

import json
import re
import time
import random
from dataclasses import dataclass, field
from pathlib import Path

from .config import EvalConfig, DEFAULT_CONFIG
from .chunk_loader import Chunk
from .llm_client import BaseLLMClient, create_llm_client


# ─── Prompts ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là chuyên gia tạo dataset đánh giá hệ thống RAG cho tài liệu giáo dục đại học.
Nhiệm vụ: sinh câu hỏi và câu trả lời mẫu từ đoạn văn bản được cung cấp.
Ngôn ngữ: Tiếng Việt.
Yêu cầu:
- Câu hỏi phải có thể trả lời được từ đoạn văn bản (không cần kiến thức bên ngoài)
- Câu trả lời mẫu phải chính xác, ngắn gọn và đầy đủ thông tin cần thiết
- Không thêm thông tin không có trong đoạn văn
- Trả lời đúng định dạng JSON yêu cầu"""

QUESTION_PROMPTS = {
    "factoid": """
Dựa vào đoạn văn bản dưới đây, hãy tạo {n} câu hỏi sự kiện cụ thể (factoid questions).
Loại câu hỏi này hỏi về thông tin cụ thể như: mã học phần, số tín chỉ, học kỳ, điều kiện tiên quyết, chuẩn đầu ra.

ĐẦU VÀO:
{context}

Trả về JSON theo định dạng:
{{
  "questions": [
    {{"question": "câu hỏi", "ground_truth": "câu trả lời ngắn gọn, chính xác"}},
    ...
  ]
}}

Chỉ trả về JSON, không giải thích thêm.
""",

    "multi_hop": """
Dựa vào đoạn văn bản dưới đây, hãy tạo {n} câu hỏi phức hợp (multi-hop questions).
Loại câu hỏi này đòi hỏi kết hợp ít nhất 2 mảnh thông tin trong đoạn văn để trả lời.
Ví dụ: "Để học học phần X ở kỳ 5, sinh viên cần đáp ứng những điều kiện gì?"

ĐẦU VÀO:
{context}

Trả về JSON:
{{
  "questions": [
    {{"question": "câu hỏi", "ground_truth": "câu trả lời tổng hợp"}},
    ...
  ]
}}
""",

    "comparative": """
Dựa vào đoạn văn bản dưới đây, hãy tạo {n} câu hỏi so sánh (comparative questions).
Câu hỏi này so sánh hai học phần, hai yêu cầu, hai chuẩn hoặc hai khái niệm khác nhau trong đoạn văn.
Nếu không có gì để so sánh, hãy tạo câu hỏi về sự khác biệt giữa các nhóm/điều kiện.

ĐẦU VÀO:
{context}

Trả về JSON:
{{
  "questions": [
    {{"question": "câu hỏi so sánh", "ground_truth": "câu trả lời nêu rõ điểm giống/khác"}},
    ...
  ]
}}
""",

    "procedural": """
Dựa vào đoạn văn bản dưới đây, hãy tạo {n} câu hỏi về quy trình/điều kiện (procedural questions).
Loại câu hỏi này hỏi về: lộ trình học tập, điều kiện để được miễn học, cách đăng ký, quy trình xét duyệt.

ĐẦU VÀO:
{context}

Trả về JSON:
{{
  "questions": [
    {{"question": "câu hỏi quy trình", "ground_truth": "câu trả lời mô tả rõ các bước/điều kiện"}},
    ...
  ]
}}
""",
}


# ─── Data models ─────────────────────────────────────────────────────────────

@dataclass
class QAPair:
    """Một cặp câu hỏi - câu trả lời mẫu."""
    question: str
    ground_truth: str
    question_type: str
    source_chunk_id: str
    source_file: str
    context: str                           # Ngữ cảnh gốc để retrieval
    hierarchy_path: str = ""
    has_table: bool = False


@dataclass
class QADataset:
    """Tập hợp các QA pairs sẵn sàng cho RAGAS evaluation."""
    pairs: list[QAPair] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total": len(self.pairs),
            "by_type": self._count_by_type(),
            "pairs": [
                {
                    "question": p.question,
                    "ground_truth": p.ground_truth,
                    "question_type": p.question_type,
                    "reference_contexts": [p.context],
                    "source_chunk_id": p.source_chunk_id,
                    "source_file": p.source_file,
                    "hierarchy_path": p.hierarchy_path,
                }
                for p in self.pairs
            ],
        }

    def _count_by_type(self) -> dict:
        counts = {}
        for p in self.pairs:
            counts[p.question_type] = counts.get(p.question_type, 0) + 1
        return counts

    def save(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu {len(self.pairs)} QA pairs → {path}")


# ─── Generator ───────────────────────────────────────────────────────────────

class QAGenerator:
    """
    Sinh câu hỏi và ground truth từ chunks bằng LLM.

    Cách dùng:
        generator = QAGenerator(client, config)
        dataset = generator.generate(chunks)
    """

    def __init__(self, llm_client: BaseLLMClient, config: EvalConfig = DEFAULT_CONFIG):
        self.client = llm_client
        self.config = config
        self._question_type_schedule = self._build_type_schedule()

    def _build_type_schedule(self) -> list[str]:
        """Tạo danh sách loại câu hỏi theo tỷ lệ đã config."""
        schedule = []
        for qtype, ratio in self.config.question_type_ratios.items():
            count = max(1, round(ratio * 100))
            schedule.extend([qtype] * count)
        return schedule

    def _pick_question_types(self, n: int) -> list[str]:
        """Chọn n loại câu hỏi theo phân phối config."""
        random.shuffle(self._question_type_schedule)
        selected = []
        for i in range(n):
            selected.append(self._question_type_schedule[i % len(self._question_type_schedule)])
        return selected

    def _parse_json_response(self, response: str) -> list[dict]:
        """Parse JSON từ response LLM, xử lý các edge case."""
        # Tìm JSON block trong response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            return []

        try:
            data = json.loads(json_match.group())
            return data.get("questions", [])
        except json.JSONDecodeError:
            # Thử sửa JSON lỗi phổ biến
            cleaned = json_match.group()
            cleaned = re.sub(r',\s*}', '}', cleaned)    # trailing comma
            cleaned = re.sub(r',\s*\]', ']', cleaned)
            try:
                data = json.loads(cleaned)
                return data.get("questions", [])
            except:
                return []

    def _generate_for_chunk(self, chunk: Chunk, n_questions: int) -> list[QAPair]:
        """Sinh câu hỏi cho một chunk."""
        pairs = []
        question_types = self._pick_question_types(n_questions)

        # Nhóm các loại câu hỏi để gọi LLM ít lần hơn
        type_counts: dict[str, int] = {}
        for qt in question_types:
            type_counts[qt] = type_counts.get(qt, 0) + 1

        for qtype, n in type_counts.items():
            prompt_template = QUESTION_PROMPTS[qtype]
            prompt = prompt_template.format(
                context=chunk.full_context,
                n=n,
            )

            try:
                response = self.client.generate(
                    prompt=prompt,
                    system_prompt=SYSTEM_PROMPT,
                )
                raw_pairs = self._parse_json_response(response)

                for raw in raw_pairs[:n]:
                    q = str(raw.get("question", "")).strip()
                    a = str(raw.get("ground_truth", "")).strip()

                    # Kiểm tra chất lượng tối thiểu
                    if len(q) < 10 or len(a) < 5:
                        continue

                    pairs.append(QAPair(
                        question=q,
                        ground_truth=a,
                        question_type=qtype,
                        source_chunk_id=chunk.chunk_id,
                        source_file=chunk.source_file,
                        context=chunk.full_context,
                        hierarchy_path=chunk.hierarchy_path,
                        has_table=chunk.has_table,
                    ))

            except Exception as e:
                print(f"    ⚠️  Lỗi sinh QA ({qtype}) cho chunk {chunk.chunk_id}: {e}")
                time.sleep(1)

        return pairs

    def generate(self, chunks: list[Chunk]) -> QADataset:
        """
        Sinh QA dataset từ danh sách chunks.

        Args:
            chunks: Danh sách chunks đã được lọc và lấy mẫu

        Returns:
            QADataset chứa tất cả QA pairs
        """
        dataset = QADataset()
        n_per_chunk = self.config.num_questions_per_chunk
        total = len(chunks)

        print(f"\n🤖 Đang sinh {n_per_chunk} câu hỏi × {total} chunks = ~{n_per_chunk * total} QA pairs...")
        print(f"   Phân phối loại câu hỏi: {self.config.question_type_ratios}\n")

        for i, chunk in enumerate(chunks, 1):
            print(f"  [{i:3d}/{total}] {chunk.chunk_id} ({chunk.source_file})")
            pairs = self._generate_for_chunk(chunk, n_per_chunk)
            dataset.pairs.extend(pairs)
            print(f"         → sinh được {len(pairs)} QA pairs")

            # Delay nhỏ để tránh overload LLM
            if i < total:
                time.sleep(0.3)

        print(f"\n✅ Tổng cộng: {len(dataset.pairs)} QA pairs")
        print(f"   Theo loại: {dataset._count_by_type()}")
        return dataset


# ─── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from .chunk_loader import load_and_prepare_chunks
    from .config import BackendType

    cfg = DEFAULT_CONFIG
    cfg.backend = BackendType.LMSTUDIO
    cfg.max_chunks_to_sample = 3
    cfg.num_questions_per_chunk = 2
    cfg.chunk_files = [
        "../data/ITE6_fix_chunks.json",
    ]

    chunks = load_and_prepare_chunks(cfg)
    client = create_llm_client(cfg)
    generator = QAGenerator(client, cfg)
    dataset = generator.generate(chunks[:3])
    dataset.save("../outputs/test_qa_dataset.json")

    # In vài mẫu
    for pair in dataset.pairs[:3]:
        print(f"\n[{pair.question_type}] {pair.question}")
        print(f"→ {pair.ground_truth}")
